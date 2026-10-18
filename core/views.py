from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .models import *


def _bandas(user):
    return Banda.objects.filter(membros__user=user)


@login_required
def home(request):
    bandas = _bandas(request.user)
    agora = timezone.now()
    minhas = (Escala.objects.filter(membro__user=request.user, evento__data_hora__gte=agora)
              .select_related("evento", "membro__banda").order_by("evento__data_hora"))
    eventos = Evento.objects.filter(banda__in=bandas, data_hora__gte=agora).select_related("banda")[:10]
    avisos = Aviso.objects.filter(banda__in=bandas).select_related("banda", "autor")[:8]
    indisp = Indisponibilidade.objects.filter(membro__user=request.user, data__gte=agora.date())
    return render(request, "home.html", dict(minhas=minhas, eventos=eventos, avisos=avisos, indisp=indisp))


@login_required
def evento(request, pk):
    ev = get_object_or_404(Evento, pk=pk, banda__in=_bandas(request.user))
    return render(request, "evento.html", dict(ev=ev, escalas=ev.escalas.select_related("membro__user"),
                                               setlist=ev.setlist.select_related("musica")))


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
    return render(request, "repertorio.html", dict(musicas=musicas, q=q))
