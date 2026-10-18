from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from .forms import EscalaForm, EventoForm, BandaForm, MembroForm, MembroNovoForm, MusicaForm, SetlistForm
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
                                             pode_criar_banda=_pode_criar_banda(request.user)))


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
