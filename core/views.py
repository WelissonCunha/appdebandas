from django.contrib import messages
from .decorators import login_required
from datetime import timedelta
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from .forms import TrocaForm, SenhaForm, SenhaResetForm, AvisoForm, EscalaForm, EventoForm, BandaForm, MembroForm, MembroNovoForm, MusicaForm, SetlistForm
from .models import *

LIDER = dict(banda__membros__papel="lider")


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
    minhas = (Escala.objects.filter(membro__user=request.user, evento__data_hora__gte=agora)
              .select_related("evento", "membro__banda").order_by("evento__data_hora"))
    eventos = Evento.objects.filter(banda__in=bandas, data_hora__gte=agora).select_related("banda")[:10]
    avisos = Aviso.objects.filter(banda__in=bandas).select_related("banda", "autor")[:8]
    indisp = Indisponibilidade.objects.filter(membro__user=request.user, data__gte=agora.date())
    return render(request, "home.html", dict(minhas=minhas, eventos=eventos, avisos=avisos, indisp=indisp,
                                             eh_lider=_eh_lider(request.user),
                                             pode_criar_banda=_pode_criar_banda(request.user),
                                             trocas_info=_trocas_info(request.user)))


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
                u = User.objects.create_user(d["username"], first_name=d["nome"], password=d["senha"])
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
        return redirect("membros")
    return render(request, "banda_form.html", dict(form=form, banda=banda))


@login_required
@require_POST
def banda_excluir(request, pk):
    _banda_lider(request, pk).delete()
    messages.success(request, "Banda excluída.")
    return redirect("home")


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
