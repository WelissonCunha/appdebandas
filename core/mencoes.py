"""Detecta @menções numa mensagem e descobre quem foi mencionado."""
import re
import unicodedata

from .models import Membro

PADRAO = re.compile(r"(?<![\w@])@([\w][\w.\-]*)")


def _n(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def mencionados(texto, banda, autor):
    """Usuários da banda citados por @usuario ou @PrimeiroNome (só se o nome for único). @todos: só líderes."""
    tokens = {t.rstrip(".-").lower() for t in PADRAO.findall(texto)}
    if not tokens:
        return []
    membros = list(Membro.objects.filter(banda=banda).select_related("user"))
    if tokens & {"todos", "todas"} and any(m.user_id == autor.id and m.papel == "lider" for m in membros):
        return [m.user for m in membros if m.user_id != autor.id]
    por_login = {m.user.username.lower(): m.user for m in membros}
    por_nome = {}
    for m in membros:
        primeiro = _n((m.user.first_name or "").split(" ")[0])
        if primeiro:
            por_nome.setdefault(primeiro, []).append(m.user)
    achados = {}
    for t in tokens:
        u = por_login.get(t)
        if u is None:
            lista = por_nome.get(_n(t), [])
            u = lista[0] if len(lista) == 1 else None
        if u and u.id != autor.id:
            achados[u.id] = u
    return list(achados.values())
