"""Contagem de mensagens não lidas por banda."""
from django.utils import timezone

from .models import LeituraMensagens, Membro, Mensagem


def contagens(user):
    """{banda_id: nº de mensagens não lidas}. Bandas sem registro começam como 'lidas até agora'."""
    bandas = list(Membro.objects.filter(user=user).values_list("banda_id", flat=True))
    if not bandas:
        return {}
    marcas = dict(LeituraMensagens.objects.filter(user=user, banda_id__in=bandas).values_list("banda_id", "ate"))
    agora = timezone.now()
    novas = [LeituraMensagens(user=user, banda_id=b, ate=agora) for b in bandas if b not in marcas]
    if novas:
        LeituraMensagens.objects.bulk_create(novas, ignore_conflicts=True)
        marcas.update({n.banda_id: agora for n in novas})
    return {b: Mensagem.objects.filter(banda_id=b, criado__gt=marcas[b]).exclude(autor=user).count() for b in bandas}


def marcar_lida(user, banda_id):
    LeituraMensagens.objects.update_or_create(user=user, banda_id=banda_id, defaults={"ate": timezone.now()})
