from django import template
from core.models import Membro

register = template.Library()


@register.simple_tag(takes_context=True)
def usuario_eh_lider(context):
    u = context["request"].user
    return u.is_authenticated and Membro.objects.filter(user=u, papel="lider").exists()
