from django.contrib import messages
from .decorators import login_required
import json
from django.http import Http404, HttpResponse, JsonResponse
from django.templatetags.static import static
from .importacao import parse_texto
from .notificacoes import notificar, vapid_keys
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse, reverse_lazy
from .forms import PerfilForm, bandas_do_lider, NotifForm, TrocaForm, SenhaForm, SenhaResetForm, AvisoForm, EscalaForm, EventoForm, BandaForm, MembroForm, MembroNovoForm, MusicaForm, SetlistForm
from .models import *

LIDER = dict(banda__membros__papel="lider")


MESES_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro",
            "Outubro", "Novembro", "Dezembro"]


def _bandas(user):
    return Banda.objects.filter(membros__user=user)


def _eh_lider(user):
    return Membro.objects.filter(user=user, papel="lider").exists()


def _pode_criar_banda(user):
    return _eh_lider(user) or not Membro.objects.filter(user=user).exists()


def _banda_lider(request, pk):
    return get_object_or_404(Banda, pk=pk, membros__user=request.user, membros__papel="lider")


def _evento_lider(request, pk):
    return get_object_or_404(Evento, pk=pk, banda__membros__user=request.user, **LIDER)


@login_required
def home(request):
    bandas = _bandas(request.user)
    agora = timezone.now()
    hoje = timezone.localdate()
    minhas = (Escala.objects.filter(membro__user=request.user, evento__data_hora__gte=agora)
              .select_related("evento", "membro__banda").order_by("evento__data_hora"))[:5]
    eventos = Evento.objects.filter(banda__in=bandas, data_hora__gte=agora).select_related("banda")[:6]
    avisos = Aviso.objects.filter(banda__in=bandas).select_related("banda", "autor")[:6]
    indisp = Indisponibilidade.objects.filter(membro__user=request.user, data__gte=hoje)
    meus_membros = (Membro.objects.filter(user=request.user).select_related("banda")
                    .annotate(n=Count("banda__membros")))
    anivers = sorted(Perfil.objects.filter(user__membros__banda__in=bandas, nascimento__month=hoje.month)
                     .select_related("user").distinct(), key=lambda p: p.nascimento.day)
    return render(request, "home.html", dict(
        minhas=minhas, eventos=eventos, avisos=avisos, indisp=indisp, meus_membros=meus_membros,
        anivers=anivers, hoje=hoje, mes_nome=MESES_PT[hoje.month - 1], eh_lider=_eh_lider(request.user),
        pode_criar_banda=_pode_criar_banda(request.user), trocas_info=_trocas_info(request.user)))


@login_required
def evento(request, pk):
    ev = get_object_or_404(Evento, pk=pk, banda__in=_bandas(request.user))
    lider = ev.banda.membros.filter(user=request.user, papel="lider").exists()
    ctx = dict(ev=ev, eh_lider=lider, escalas=ev.escalas.select_related("membro__user"),
               setlist=ev.setlist.select_related("musica"))
    if lider:
        ctx["escala_form"] = EscalaForm(banda=ev.banda)
        ctx["setlist_form"] = SetlistForm(banda=ev.banda)
    return render(request, "evento.html", ctx)


@login_required
def responder(request, pk):
    esc = get_object_or_404(Escala, pk=pk, membro__user=request.user)
    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao in ("confirmado", "recusado"):
            esc.status = acao
            esc.obs = request.POST.get("obs", "")[:200]
            esc.save()
            messages.success(request, "Resposta registrada!")
    if request.POST.get("voltar") == "minhas":
        return redirect("minhas_escalas")
    return redirect("evento", pk=esc.evento_id)


@login_required
def indisponibilidade(request):
    if request.method == "POST":
        membro = Membro.objects.filter(user=request.user).first()
        if membro and request.POST.get("data"):
            Indisponibilidade.objects.create(membro=membro, data=request.POST["data"],
                                             motivo=request.POST.get("motivo", ""))
            messages.success(request, "Indisponibilidade registrada.")
    return redirect("home")


@login_required
def repertorio(request):
    q = request.GET.get("q", "")
    musicas = Musica.objects.filter(banda__in=_bandas(request.user))
    if q:
        musicas = musicas.filter(titulo__icontains=q) | musicas.filter(artista__icontains=q)
    return render(request, "repertorio.html", dict(musicas=musicas, q=q, eh_lider=_eh_lider(request.user)))


# ---------- gestão do líder ----------

@login_required
def evento_form(request, pk=None):
    ev = _evento_lider(request, pk) if pk else None
    if not ev and not _eh_lider(request.user):
        messages.error(request, "Apenas líderes podem criar eventos.")
        return redirect("home")
    form = EventoForm(request.POST or None, instance=ev, user=request.user)
    if request.method == "POST" and form.is_valid():
        ev = form.save()
        messages.success(request, "Evento salvo!")
        return redirect("evento", pk=ev.pk)
    return render(request, "evento_form.html", dict(form=form, ev=ev))


@login_required
@require_POST
def evento_excluir(request, pk):
    _evento_lider(request, pk).delete()
    messages.success(request, "Evento excluído.")
    return redirect("eventos")


@login_required
@require_POST
def escala_add(request, pk):
    ev = _evento_lider(request, pk)
    form = EscalaForm(request.POST, banda=ev.banda)
    if form.is_valid():
        e = form.save(commit=False)
        e.evento = ev
        e.save()
        notificar([e.membro.user], "Você foi escalado!", f"{e.funcao} em {ev.titulo} — {_fmt(ev.data_hora)}",
                  f"/evento/{ev.pk}/", exceto=request.user)
    else:
        messages.error(request, "Escolha o membro e informe a função.")
    return redirect("evento", pk=pk)


@login_required
@require_POST
def escala_del(request, pk):
    esc = get_object_or_404(Escala, pk=pk, evento__banda__membros__user=request.user,
                            evento__banda__membros__papel="lider")
    ev_id = esc.evento_id
    esc.delete()
    return redirect("evento", pk=ev_id)


@login_required
@require_POST
def setlist_add(request, pk):
    ev = _evento_lider(request, pk)
    form = SetlistForm(request.POST, banda=ev.banda)
    if form.is_valid():
        item = form.save(commit=False)
        item.evento = ev
        item.ordem = (ev.setlist.aggregate(m=Max("ordem"))["m"] or 0) + 1
        item.save()
    else:
        messages.error(request, "Escolha uma música.")
    return redirect("evento", pk=pk)


def _item_lider(request, pk):
    return get_object_or_404(ItemSetlist, pk=pk, evento__banda__membros__user=request.user,
                             evento__banda__membros__papel="lider")


@login_required
@require_POST
def setlist_del(request, pk):
    item = _item_lider(request, pk)
    ev_id = item.evento_id
    item.delete()
    return redirect("evento", pk=ev_id)


@login_required
@require_POST
def setlist_mover(request, pk):
    item = _item_lider(request, pk)
    itens = list(item.evento.setlist.all())
    i = [x.pk for x in itens].index(item.pk)
    j = i - 1 if request.POST.get("dir") == "up" else i + 1
    if 0 <= j < len(itens):
        itens[i], itens[j] = itens[j], itens[i]
    for n, x in enumerate(itens, 1):
        ItemSetlist.objects.filter(pk=x.pk).update(ordem=n)
    return redirect("evento", pk=item.evento_id)


@login_required
def musica_form(request, pk=None):
    mus = (get_object_or_404(Musica, pk=pk, banda__membros__user=request.user, **LIDER) if pk else None)
    if not mus and not _eh_lider(request.user):
        messages.error(request, "Apenas líderes podem cadastrar músicas.")
        return redirect("home")
    form = MusicaForm(request.POST or None, instance=mus, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Música salva!")
        return redirect("repertorio")
    return render(request, "musica_form.html", dict(form=form, mus=mus))


@login_required
@require_POST
def musica_excluir(request, pk):
    get_object_or_404(Musica, pk=pk, banda__membros__user=request.user, **LIDER).delete()
    messages.success(request, "Música excluída.")
    return redirect("repertorio")


# ---------- membros ----------

def _membro_lider(request, pk):
    return get_object_or_404(Membro, pk=pk, banda__membros__user=request.user, **LIDER)


def _ultimo_lider(m):
    return m.papel == "lider" and not m.banda.membros.filter(papel="lider").exclude(pk=m.pk).exists()


@login_required
def membros(request):
    if not _eh_lider(request.user):
        return redirect("home")
    bandas = (Banda.objects.filter(membros__user=request.user, membros__papel="lider")
              .prefetch_related("membros__user"))
    return render(request, "membros.html", dict(bandas=bandas))


@login_required
def membro_novo(request):
    if not _eh_lider(request.user):
        return redirect("home")
    form = MembroNovoForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        User = get_user_model()
        u = User.objects.filter(username=d["username"]).first()
        if not u and not d["senha"]:
            form.add_error("senha", "Informe uma senha para o novo login.")
        else:
            if not u:
                u = User.objects.create_user(d["username"], email=d["email"], first_name=d["nome"], password=d["senha"])
                Perfil.objects.update_or_create(user=u, defaults={"trocar_senha": True})
            _, criado = Membro.objects.get_or_create(
                user=u, banda=d["banda"], defaults=dict(papel=d["papel"], instrumentos=d["instrumentos"]))
            if criado:
                messages.success(request, "Membro adicionado!")
                return redirect("membros")
            form.add_error("username", "Essa pessoa já faz parte da banda.")
    return render(request, "membro_form.html", dict(form=form, m=None))


@login_required
def membro_editar(request, pk):
    m = _membro_lider(request, pk)
    form = MembroForm(request.POST or None, instance=m)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["papel"] != "lider" and _ultimo_lider(m):
            form.add_error("papel", "A banda precisa de pelo menos um líder.")
        else:
            form.save()
            messages.success(request, "Membro atualizado!")
            return redirect("membros")
    return render(request, "membro_form.html", dict(form=form, m=m))


@login_required
@require_POST
def membro_excluir(request, pk):
    m = _membro_lider(request, pk)
    if _ultimo_lider(m):
        messages.error(request, "Não dá para remover o único líder da banda.")
    else:
        m.delete()
        messages.success(request, "Membro removido.")
    return redirect("membros")


# ---------- bandas ----------

@login_required
def banda_form(request, pk=None):
    banda = _banda_lider(request, pk) if pk else None
    if not banda and not _pode_criar_banda(request.user):
        messages.error(request, "Apenas líderes podem criar bandas.")
        return redirect("home")
    form = BandaForm(request.POST or None, instance=banda)
    if request.method == "POST" and form.is_valid():
        novo = banda is None
        banda = form.save()
        if novo:
            Membro.objects.create(user=request.user, banda=banda, papel="lider")
        messages.success(request, "Banda salva!")
        return redirect("bandas")
    return render(request, "banda_form.html", dict(form=form, banda=banda))


@login_required
@require_POST
def banda_excluir(request, pk):
    _banda_lider(request, pk).delete()
    messages.success(request, "Banda excluída.")
    return redirect("bandas")


@login_required
def eventos_lista(request):
    if not _eh_lider(request.user):
        return redirect("home")
    qs = (Evento.objects.filter(banda__membros__user=request.user, banda__membros__papel="lider")
          .select_related("banda").distinct())
    agora = timezone.now()
    return render(request, "eventos.html", dict(futuros=qs.filter(data_hora__gte=agora).order_by("data_hora"),
                                                passados=qs.filter(data_hora__lt=agora).order_by("-data_hora")))


# ---------- avisos ----------

def _aviso_lider(request, pk):
    return get_object_or_404(Aviso, pk=pk, banda__membros__user=request.user, **LIDER)


@login_required
def avisos_lista(request):
    if not _eh_lider(request.user):
        return redirect("home")
    avisos = (Aviso.objects.filter(banda__membros__user=request.user, banda__membros__papel="lider")
              .select_related("banda", "autor").distinct())
    return render(request, "avisos.html", dict(avisos=avisos))


@login_required
def aviso_form(request, pk=None):
    aviso = _aviso_lider(request, pk) if pk else None
    if not aviso and not _eh_lider(request.user):
        messages.error(request, "Apenas líderes podem postar avisos.")
        return redirect("home")
    form = AvisoForm(request.POST or None, instance=aviso, user=request.user)
    if request.method == "POST" and form.is_valid():
        novo = form.save(commit=False)
        if not aviso:
            novo.autor = request.user
        novo.save()
        if not aviso:
            notificar([x.user for x in novo.banda.membros.select_related("user")], f"Novo aviso — {novo.banda.nome}",
                      novo.texto[:140], "/", exceto=request.user)
        messages.success(request, "Aviso salvo!")
        return redirect("avisos")
    return render(request, "aviso_form.html", dict(form=form, aviso=aviso))


@login_required
@require_POST
def aviso_fixar(request, pk):
    aviso = _aviso_lider(request, pk)
    aviso.fixado = not aviso.fixado
    aviso.save(update_fields=["fixado"])
    return redirect("avisos")


@login_required
@require_POST
def aviso_excluir(request, pk):
    _aviso_lider(request, pk).delete()
    messages.success(request, "Aviso excluído.")
    return redirect("avisos")


@login_required
def gerenciar(request):
    if not _eh_lider(request.user):
        return redirect("home")
    bandas = Banda.objects.filter(membros__user=request.user, membros__papel="lider")
    stats = dict(
        eventos=Evento.objects.filter(banda__in=bandas, data_hora__gte=timezone.now()).count(),
        musicas=Musica.objects.filter(banda__in=bandas).count(),
        membros=Membro.objects.filter(banda__in=bandas).count(),
        bandas=bandas.count(),
        avisos=Aviso.objects.filter(banda__in=bandas).count(),
        trocas=TrocaEscala.objects.filter(status="aberta", escala__evento__banda__in=bandas,
                                          escala__evento__data_hora__gte=timezone.now()).count(),
    )
    return render(request, "gerenciar.html", dict(bandas=bandas, stats=stats))


# ---------- senhas ----------

class AlterarSenhaView(SuccessMessageMixin, PasswordChangeView):
    template_name = "senha_form.html"
    form_class = SenhaForm
    success_url = reverse_lazy("home")
    success_message = "Senha alterada com sucesso!"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["forcado"] = Perfil.objects.filter(user=self.request.user, trocar_senha=True).exists()
        return ctx

    def form_valid(self, form):
        resp = super().form_valid(form)
        Perfil.objects.filter(user=self.request.user).update(trocar_senha=False)
        return resp


@login_required
def membro_senha(request, pk):
    m = _membro_lider(request, pk)
    alvo = m.user
    if alvo.is_staff or alvo.is_superuser or Membro.objects.filter(user=alvo, papel="lider").exists():
        messages.error(request, "Não dá para redefinir a senha de líderes ou administradores aqui. "
                                "Cada um altera a própria em 🔑 Senha.")
        return redirect("membro_editar", pk=pk)
    form = SenhaResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        alvo.set_password(form.cleaned_data["nova_senha"])
        alvo.save()
        Perfil.objects.update_or_create(user=alvo, defaults={"trocar_senha": True})
        messages.success(request, "Senha redefinida. A pessoa foi desconectada e deve entrar com a nova senha.")
        return redirect("membros")
    return render(request, "membro_senha.html", dict(form=form, m=m))


# ---------- troca de escala ----------

def _membro_na_banda(user, banda):
    return Membro.objects.filter(user=user, banda=banda).first()


def _pode_cobrir(t, m):
    """Devolve None se o membro m pode assumir a troca t; senão, o motivo."""
    ev = t.escala.evento
    if t.status != "aberta":
        return "Este pedido não está mais aberto."
    if ev.data_hora <= timezone.now():
        return "O evento já passou."
    if m is None or m.banda_id != ev.banda_id:
        return "Você não faz parte desta banda."
    if m.pk == t.solicitante_id:
        return "Foi você quem pediu."
    if t.destinatario_id and t.destinatario_id != m.pk:
        return "Pedido direcionado a outra pessoa."
    if ev.escalas.filter(membro=m).exists():
        return "Você já está escalado neste evento."
    if Indisponibilidade.objects.filter(membro=m, data=timezone.localtime(ev.data_hora).date()).exists():
        return "Você marcou indisponibilidade nesta data."
    return None


def _trocas_info(user):
    if not _eh_lider(user):
        return None
    qs = TrocaEscala.objects.filter(escala__evento__banda__membros__user=user,
                                    escala__evento__banda__membros__papel="lider")
    agora = timezone.now()
    abertas = qs.filter(status="aberta", escala__evento__data_hora__gte=agora).distinct().count()
    aceitas = qs.filter(status="aceita", resolvida__gte=agora - timedelta(days=7)).distinct().count()
    return dict(abertas=abertas, aceitas=aceitas) if abertas or aceitas else None


@login_required
def troca_pedir(request, pk):
    esc = get_object_or_404(Escala.objects.select_related("evento__banda", "membro__user"),
                            pk=pk, membro__user=request.user)
    if esc.evento.data_hora <= timezone.now():
        messages.error(request, "Esse evento já passou.")
        return redirect("home")
    if esc.trocas.filter(status="aberta").exists():
        messages.error(request, "Você já tem um pedido de troca aberto para esta escala.")
        return redirect("trocas")
    form = TrocaForm(request.POST or None, escala=esc)
    if request.method == "POST" and form.is_valid():
        t = form.save(commit=False)
        t.escala, t.solicitante = esc, esc.membro
        t.save()
        messages.success(request, "Pedido de troca enviado! O líder é avisado quando alguém aceitar.")
        return redirect("trocas")
    return render(request, "troca_form.html", dict(form=form, esc=esc))


@login_required
def trocas(request):
    base = TrocaEscala.objects.select_related("escala__evento__banda", "escala__membro__user",
                                              "solicitante__user", "destinatario__user", "substituto__user")
    abertas = (base.filter(status="aberta", escala__evento__data_hora__gte=timezone.now(),
                           escala__evento__banda__membros__user=request.user)
               .exclude(solicitante__user=request.user)
               .filter(Q(destinatario__isnull=True) | Q(destinatario__user=request.user))
               .distinct().order_by("escala__evento__data_hora"))
    para_mim = [dict(t=t, motivo=_pode_cobrir(t, _membro_na_banda(request.user, t.escala.evento.banda)))
                for t in abertas]
    minhas = base.filter(solicitante__user=request.user).order_by("-criado")[:15]
    lider = None
    if _eh_lider(request.user):
        lider = (base.filter(escala__evento__banda__membros__user=request.user,
                             escala__evento__banda__membros__papel="lider")
                 .distinct().order_by("-criado")[:30])
    return render(request, "trocas.html", dict(para_mim=para_mim, minhas=minhas, lider=lider))


@login_required
@require_POST
def troca_aceitar(request, pk):
    with transaction.atomic():
        t = get_object_or_404(TrocaEscala.objects.select_for_update(), pk=pk)
        ev = t.escala.evento
        m = _membro_na_banda(request.user, ev.banda)
        erro = _pode_cobrir(t, m)
        if erro:
            messages.error(request, erro)
            return redirect("trocas")
        esc = t.escala
        esc.membro, esc.status, esc.obs = m, "confirmado", "Cobrindo troca"
        esc.save()
        t.status, t.substituto, t.resolvida = "aceita", m, timezone.now()
        t.save()
    quem = m.user.get_full_name() or m.user.username
    sol = t.solicitante.user
    notificar([sol], "Sua troca foi aceita", f"{quem} vai cobrir {esc.funcao} em {ev.titulo}.", f"/evento/{ev.pk}/", exceto=request.user)
    notificar([x.user for x in ev.banda.membros.filter(papel="lider").select_related("user") if x.user_id != sol.pk],
              "Troca de escala aceita",
              f"{quem} assumiu {esc.funcao} de {sol.get_full_name() or sol.username} em {ev.titulo} ({_fmt(ev.data_hora)}).",
              f"/evento/{ev.pk}/", exceto=request.user)
    messages.success(request, f"Você assumiu {esc.funcao} em {ev.titulo}!")
    return redirect("trocas")


@login_required
@require_POST
def troca_cancelar(request, pk):
    t = get_object_or_404(TrocaEscala, pk=pk, status="aberta")
    dono = t.solicitante.user_id == request.user.id
    lider = t.escala.evento.banda.membros.filter(user=request.user, papel="lider").exists()
    if not (dono or lider):
        messages.error(request, "Você não pode cancelar este pedido.")
    else:
        t.status, t.resolvida = "cancelada", timezone.now()
        t.save()
        messages.success(request, "Pedido cancelado.")
    return redirect("trocas")


@login_required
def evento_exportar(request, pk):
    ev = get_object_or_404(Evento, pk=pk, banda__in=_bandas(request.user))
    return render(request, "evento_exportar.html", dict(ev=ev, escalas=ev.escalas.select_related("membro__user"),
                                                        setlist=ev.setlist.select_related("musica"),
                                                        gerado=timezone.localtime()))


@login_required
def minhas_escalas(request):
    agora = timezone.now()
    qs = (Escala.objects.filter(membro__user=request.user).select_related("evento__banda")
          .annotate(troca_aberta=Exists(TrocaEscala.objects.filter(escala=OuterRef("pk"), status="aberta"))))
    proximas = qs.filter(evento__data_hora__gte=agora).order_by("evento__data_hora")
    passadas = qs.filter(evento__data_hora__lt=agora).order_by("-evento__data_hora")[:20]
    return render(request, "minhas_escalas.html", dict(
        proximas=proximas, passadas=passadas, pendentes=proximas.filter(status="pendente").count()))


@login_required
def bandas_lista(request):
    if not _eh_lider(request.user):
        return redirect("home")
    bandas = (Banda.objects.filter(membros__user=request.user, membros__papel="lider")
              .annotate(n_membros=Count("membros", distinct=True), n_eventos=Count("eventos", distinct=True),
                        n_musicas=Count("musicas", distinct=True)).order_by("nome"))
    return render(request, "bandas.html", dict(bandas=bandas))


# ---------- notificações / PWA ----------

def _fmt(dt):
    return timezone.localtime(dt).strftime("%d/%m às %H:%M")


@login_required
def notificacoes(request):
    perfil = Perfil.objects.filter(user=request.user).first()
    inicial = dict(email=request.user.email, notif_email=perfil.notif_email if perfil else True,
                   notif_push=perfil.notif_push if perfil else True)
    form = NotifForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        request.user.email = d["email"]
        request.user.save(update_fields=["email"])
        Perfil.objects.update_or_create(user=request.user, defaults=dict(
            notif_email=d["notif_email"], notif_push=d["notif_push"]))
        messages.success(request, "Preferências salvas!")
        return redirect("notificacoes")
    try:
        chave = vapid_keys()[0]
    except Exception:
        chave = ""
    return render(request, "notificacoes.html", dict(form=form, chave=chave, n_disp=request.user.push_subs.count()))


@login_required
@require_POST
def push_inscrever(request):
    try:
        d = json.loads(request.body)
        PushSub.objects.update_or_create(endpoint=d["endpoint"], defaults=dict(
            user=request.user, p256dh=d["keys"]["p256dh"], auth=d["keys"]["auth"]))
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"ok": False}, status=400)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def push_cancelar(request):
    try:
        PushSub.objects.filter(endpoint=json.loads(request.body).get("endpoint"), user=request.user).delete()
    except (ValueError, AttributeError):
        return JsonResponse({"ok": False}, status=400)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def push_teste(request):
    notificar([request.user], "Notificação de teste", "Se você recebeu isso, está funcionando! 🎸", "/notificacoes/")
    messages.success(request, "Teste enviado. Pode levar alguns segundos (sem e-mail configurado, ele aparece no terminal).")
    return redirect("notificacoes")


def manifest(request):
    icones = [dict(src=static("core/icons/icon-192.png"), sizes="192x192", type="image/png", purpose="any"),
              dict(src=static("core/icons/icon-512.png"), sizes="512x512", type="image/png", purpose="any"),
              dict(src=static("core/icons/icon-maskable-512.png"), sizes="512x512", type="image/png", purpose="maskable")]
    return JsonResponse(dict(name="Bandas", short_name="Bandas", description="Escalas, repertório e avisos da banda",
                             start_url="/", scope="/", display="standalone", lang="pt-BR",
                             theme_color="#5b4bdb", background_color="#f6f6f9", icons=icones),
                        content_type="application/manifest+json")


def service_worker(request):
    resp = render(request, "sw.js", content_type="application/javascript")
    resp["Cache-Control"] = "no-cache"
    return resp


# ---------- importar calendário (texto colado) ----------

def _aware(s):
    try:
        return timezone.make_aware(datetime.strptime(s, "%Y-%m-%dT%H:%M"))
    except (ValueError, TypeError):
        return None


@login_required
def importar_eventos(request):
    if not _eh_lider(request.user):
        return redirect("home")
    bandas = bandas_do_lider(request.user)
    ano_atual = timezone.localdate().year
    ctx = dict(bandas=bandas, tipos=Evento.TIPOS, ano=ano_atual, hora="19:00", tipo="culto", texto="",
               importacoes=(ImportacaoEventos.objects.filter(banda__in=bandas).select_related("banda")
                            .annotate(n=Count("eventos")).order_by("-criado")[:10]))
    if request.method != "POST":
        return render(request, "importar.html", ctx)
    banda = bandas.filter(pk=request.POST.get("banda") or 0).first()
    if not banda:
        messages.error(request, "Escolha uma banda.")
        return render(request, "importar.html", ctx)
    tipos_validos = {t for t, _ in Evento.TIPOS}

    if request.POST.get("acao") == "confirmar":
        criados = ignorados = 0
        imp = None
        for i in range(int(request.POST.get("total", 0) or 0)):
            if not request.POST.get(f"ok_{i}"):
                continue
            titulo = request.POST.get(f"titulo_{i}", "").strip()[:150]
            quando = _aware(request.POST.get(f"quando_{i}"))
            tipo = request.POST.get(f"tipo_{i}")
            if not titulo or not quando or tipo not in tipos_validos or Evento.objects.filter(
                    banda=banda, titulo__iexact=titulo, data_hora__date=timezone.localtime(quando).date()).exists():
                ignorados += 1
                continue
            imp = imp or ImportacaoEventos.objects.create(banda=banda, autor=request.user)
            Evento.objects.create(banda=banda, titulo=titulo, tipo=tipo, data_hora=quando, importacao=imp,
                                  local=request.POST.get(f"local_{i}", "").strip()[:150])
            criados += 1
        if criados:
            messages.success(request, f"{criados} evento(s) importado(s)!" + (f" {ignorados} ignorado(s)." if ignorados else ""))
            return redirect("eventos")
        messages.error(request, "Nenhum evento foi importado. Confira os itens marcados (título e data).")
        return redirect("importar_eventos")

    # pré-visualização
    try:
        ano = int(request.POST.get("ano") or ano_atual)
    except ValueError:
        ano = ano_atual
    hora = request.POST.get("hora") or "19:00"
    tipo_padrao = request.POST.get("tipo") if request.POST.get("tipo") in tipos_validos else "culto"
    linhas = []
    for i, it in enumerate(parse_texto(request.POST.get("texto", ""), ano)):
        quando, dup = "", False
        if it["data"]:
            h, mi = it["hora"] or tuple(int(x) for x in hora.split(":")[:2])
            y, mo, d = it["data"]
            quando = f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}"
            dup = Evento.objects.filter(banda=banda, titulo__iexact=it["titulo"], data_hora__date=datetime(y, mo, d).date()).exists()
        linhas.append(dict(i=i, quando=quando, dup=dup, tipo=it["tipo"] or tipo_padrao,
                           marcado=not it["erro"] and not dup, **{k: it[k] for k in ("linha", "titulo", "local", "erro")}))
    if not linhas:
        messages.error(request, "Cole o texto do calendário na caixa.")
        return render(request, "importar.html", ctx)
    return render(request, "importar.html", dict(ctx, banda=banda, linhas=linhas, total=len(linhas)))


@login_required
@require_POST
def importacao_desfazer(request, pk):
    imp = get_object_or_404(ImportacaoEventos, pk=pk, banda__membros__user=request.user, banda__membros__papel="lider")
    n = imp.eventos.count()
    imp.eventos.all().delete()
    imp.delete()
    messages.success(request, f"Importação desfeita: {n} evento(s) removido(s).")
    return redirect("importar_eventos")


# ---------- exclusão em lote ----------

def _ids(request):
    return [int(i) for i in request.POST.getlist("ids") if i.isdigit()]


@login_required
@require_POST
def evento_excluir_lote(request):
    qs = Evento.objects.filter(pk__in=_ids(request), banda__membros__user=request.user, **LIDER)
    n = qs.count()
    qs.delete()
    messages.success(request, f"{n} evento(s) excluído(s).") if n else messages.error(request, "Nenhum evento selecionado.")
    return redirect("eventos")


@login_required
@require_POST
def musica_excluir_lote(request):
    qs = Musica.objects.filter(pk__in=_ids(request), banda__membros__user=request.user, **LIDER)
    n = qs.count()
    qs.delete()
    messages.success(request, f"{n} música(s) excluída(s).") if n else messages.error(request, "Nenhuma música selecionada.")
    return redirect("repertorio")


@login_required
@require_POST
def membro_excluir_lote(request):
    alvos = (Membro.objects.filter(pk__in=_ids(request), banda__membros__user=request.user, **LIDER)
             .select_related("banda"))
    por_banda = {}
    for m in alvos:
        por_banda.setdefault(m.banda_id, []).append(m)
    removidos = bloqueados = 0
    for banda_id, grupo in por_banda.items():
        lideres = Membro.objects.filter(banda_id=banda_id, papel="lider").count()
        lideres_alvo = sum(1 for m in grupo if m.papel == "lider")
        for m in grupo:
            if m.user_id == request.user.id or (m.papel == "lider" and lideres - lideres_alvo <= 0):
                bloqueados += 1
                continue
            m.delete()
            removidos += 1
    if removidos:
        messages.success(request, f"{removidos} membro(s) removido(s).")
    if bloqueados:
        messages.error(request, f"{bloqueados} não foi(ram) removido(s): você não pode remover a si mesmo "
                                "nem deixar a banda sem líder.")
    if not removidos and not bloqueados:
        messages.error(request, "Nenhum membro selecionado.")
    return redirect("membros")


# ---------- perfil, foto e membros ----------

@login_required
def perfil(request):
    p = Perfil.objects.filter(user=request.user).first()
    form = PerfilForm(request.POST or None, initial=dict(nome=request.user.get_full_name(),
                                                         nascimento=p.nascimento if p else None))
    if request.method == "POST" and form.is_valid():
        request.user.first_name, request.user.last_name = form.cleaned_data["nome"].strip(), ""
        request.user.save(update_fields=["first_name", "last_name"])
        Perfil.objects.update_or_create(user=request.user, defaults=dict(nascimento=form.cleaned_data["nascimento"]))
        messages.success(request, "Dados salvos!")
        return redirect("perfil")
    return render(request, "perfil.html", dict(
        form=form, foto_em=p.foto_em if p else None, nome=request.user.get_full_name() or request.user.username,
        meus_membros=Membro.objects.filter(user=request.user).select_related("banda")))


@login_required
@require_POST
def perfil_foto(request):
    if request.POST.get("remover"):
        FotoPerfil.objects.filter(user=request.user).delete()
        Perfil.objects.update_or_create(user=request.user, defaults=dict(foto_em=None))
        messages.success(request, "Foto removida.")
        return redirect("perfil")
    arq = request.FILES.get("foto")
    dados = arq.read() if arq else b""
    if not dados or len(dados) > 300_000 or dados[:3] != b"\xff\xd8\xff":
        return JsonResponse({"ok": False}, status=400)
    FotoPerfil.objects.update_or_create(user=request.user, defaults=dict(dados=dados))
    Perfil.objects.update_or_create(user=request.user, defaults=dict(foto_em=timezone.now()))
    return JsonResponse({"ok": True})


@login_required
def foto(request, pk):
    if pk != request.user.pk and not Membro.objects.filter(user_id=pk, banda__membros__user=request.user).exists():
        raise Http404
    f = get_object_or_404(FotoPerfil, user_id=pk)
    resp = HttpResponse(bytes(f.dados), content_type="image/jpeg")
    resp["Cache-Control"] = "private, max-age=86400"
    return resp


def _banda_escolhida(request):
    bandas = list(Banda.objects.filter(membros__user=request.user).order_by("nome"))
    alvo = next((b for b in bandas if str(b.pk) == request.GET.get("banda")), bandas[0] if bandas else None)
    return bandas, alvo


@login_required
def equipe(request):
    bandas, banda = _banda_escolhida(request)
    membros = (Membro.objects.filter(banda=banda).select_related("user__perfil")
               .order_by("papel", "user__first_name", "user__username")) if banda else []
    pode = bool(banda) and banda.membros.filter(user=request.user, papel="lider").exists()
    return render(request, "equipe.html", dict(bandas=bandas, banda=banda, membros=membros, pode_gerenciar=pode))


# ---------- mensagens ----------

@login_required
def mensagens(request):
    bandas, banda = _banda_escolhida(request)
    msgs, lider_banda = [], False
    if banda:
        msgs = list(banda.mensagens.select_related("autor").order_by("-criado")[:80])[::-1]
        fotos = dict(Perfil.objects.filter(user_id__in={x.autor_id for x in msgs if x.autor_id})
                     .values_list("user_id", "foto_em"))
        for x in msgs:
            x.foto_em = fotos.get(x.autor_id)
        lider_banda = banda.membros.filter(user=request.user, papel="lider").exists()
    return render(request, "mensagens.html", dict(bandas=bandas, banda=banda, msgs=msgs, lider_banda=lider_banda))


@login_required
@require_POST
def mensagem_enviar(request):
    bid = request.POST.get("banda", "")
    banda = get_object_or_404(Banda, pk=int(bid) if bid.isdigit() else 0, membros__user=request.user)
    texto = request.POST.get("texto", "").strip()[:1000]
    if texto:
        Mensagem.objects.create(banda=banda, autor=request.user, texto=texto)
    return redirect(reverse("mensagens") + f"?banda={banda.pk}")


@login_required
@require_POST
def mensagem_excluir(request, pk):
    msg = get_object_or_404(Mensagem, pk=pk, banda__membros__user=request.user)
    if msg.autor_id == request.user.id or msg.banda.membros.filter(user=request.user, papel="lider").exists():
        msg.delete()
    return redirect(reverse("mensagens") + f"?banda={msg.banda_id}")
