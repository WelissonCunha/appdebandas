from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import EscalaForm, EventoForm, MusicaForm, SetlistForm
from .models import *

LIDER = dict(banda__membros__papel="lider")


def _bandas(user):
    return Banda.objects.filter(membros__user=user)


def _eh_lider(user):
    return Membro.objects.filter(user=user, papel="lider").exists()


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
                                             eh_lider=_eh_lider(request.user)))


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
    return redirect("home")


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
