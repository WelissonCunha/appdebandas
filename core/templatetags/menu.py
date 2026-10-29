import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.utils.html import format_html
from core.models import Membro

register = template.Library()


@register.simple_tag(takes_context=True)
def usuario_eh_lider(context):
    u = context["request"].user
    return u.is_authenticated and Membro.objects.filter(user=u, papel="lider").exists()


@register.simple_tag
def avatar(user_id, nome, foto_em=None, tamanho=40):
    """Foto redonda do usuário ou, sem foto, um círculo com a inicial do nome."""
    if foto_em:
        return format_html('<img class="av" src="{}?v={}" width="{}" height="{}" alt="">',
                           reverse("foto", args=[user_id]), int(foto_em.timestamp()), tamanho, tamanho)
    ini = (str(nome or "?").strip()[:1] or "?").upper()
    return format_html('<span class="av ini" style="width:{0}px;height:{0}px;font-size:{1}px">{2}</span>',
                       tamanho, int(int(tamanho) * 0.42), ini)


@register.simple_tag
def avatar_banda(banda_id, nome, foto_em=None, tamanho=44):
    """Foto da banda (ou a inicial do nome) em círculo."""
    if foto_em:
        return format_html('<img class="av" src="{}?v={}" width="{}" height="{}" alt="">',
                           reverse("banda_foto", args=[banda_id]), int(foto_em.timestamp()), tamanho, tamanho)
    ini = (str(nome or "?").strip()[:1] or "?").upper()
    return format_html('<span class="av ini" style="width:{0}px;height:{0}px;font-size:{1}px">{2}</span>',
                       tamanho, int(int(tamanho) * 0.42), ini)


@register.simple_tag(takes_context=True)
def nao_lidas(context):
    """Total de mensagens não lidas do usuário (uma consulta por página)."""
    request = context.get("request")
    if request is None or not request.user.is_authenticated:
        return 0
    if not hasattr(request, "_nao_lidas"):
        from core.leitura import contagens
        request._nao_lidas = sum(contagens(request.user).values())
    return request._nao_lidas


@register.filter
def mencoes(texto):
    """Escapa o texto e destaca as @menções."""
    return mark_safe(re.sub(r"(?<![\w@])@([\w][\w.\-]*)", r'<b class="men">@\1</b>', escape(texto)))
