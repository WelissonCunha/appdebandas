"""Lê texto colado de um calendário e devolve uma lista de eventos candidatos."""
import re
from collections import deque
from datetime import datetime

MESES = {"janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
         "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
_MES = "|".join(sorted(MESES, key=len, reverse=True))
DIAS = r"(?:segunda|terça|terca|quarta|quinta|sexta|sábado|sabado|domingo|seg|ter|qua|qui|sex|sáb|sab|dom)(?:-feira)?"
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
_TXT = re.compile(rf"(?<!\d)(\d{{1,2}})\s*(?:de\s+)?({_MES})\b(?:\s*(?:de\s*)?(\d{{4}}))?", re.I)
_NUM = re.compile(r"(?<!\d)(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2,4}))?(?!\d)")
_HORA = re.compile(r"(?<!\d)(\d{1,2})\s*(?:h(?![^\W\d_])|:)\s*(\d{2})?(?!\d)|(?<!\d)(\d{1,2})\s*horas?\b", re.I)
_CAB = re.compile(rf"^\W*({_MES})(?:\s*(?:de|/|-)?\s*(\d{{4}}))?\W*$", re.I)
_MULTI = re.compile(rf"^\s*(?:{DIAS}[,\s]+)?(\d{{1,2}})\s*(e|a|,)\s*(\d{{1,2}})(?![\d/.h:])\s*[-–—:)]\s*(.+)$", re.I)
_DIA = re.compile(rf"^\s*(?:{DIAS}[,\s]+)?(\d{{1,2}})(?![\d/.h:])\s*(?:[-–—:)]\s*|\s+)", re.I)


def _ok(y, m, d):
    try:
        datetime(y, m, d)
        return True
    except ValueError:
        return False


def _achar_data(l, ano):
    for m in _ISO.finditer(l):
        y, mo, d = map(int, m.groups())
        if _ok(y, mo, d):
            return (y, mo, d), m.span()
    for m in _TXT.finditer(l):
        d, mo, y = int(m.group(1)), MESES[m.group(2).lower()], int(m.group(3) or ano)
        if _ok(y, mo, d):
            return (y, mo, d), m.span()
    for m in _NUM.finditer(l):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3) or ano)
        y = y + 2000 if y < 100 else y
        if _ok(y, mo, d):
            return (y, mo, d), m.span()
    return None, None


def tipo_por_titulo(t):
    b = t.lower()
    if "ensaio" in b:
        return "ensaio"
    if any(k in b for k in ("show", "apresenta", "concerto", "festival")):
        return "show"
    if any(k in b for k in ("culto", "missa", "celebra", "louvor", "santa ceia", "vig")):
        return "culto"
    return None


def parse_texto(texto, ano):
    """Cada item: linha, titulo, data=(a,m,d)|None, hora=(h,m)|None, local, tipo|None, erro."""
    itens, mes_ctx, ano_ctx = [], None, ano
    fila = deque(texto.splitlines())
    while fila:
        bruto = fila.popleft()
        l = bruto.strip()
        if not l:
            continue
        l = re.sub(r"^(?:[-*•·]+|\d+[.)])\s+", "", l)
        cab = _CAB.match(l)
        if cab:
            mes_ctx = MESES[cab.group(1).lower()]
            ano_ctx = int(cab.group(2)) if cab.group(2) else ano_ctx
            continue
        if mes_ctx:
            mm = _MULTI.match(l)
            if mm:
                d1, sep, d2 = int(mm.group(1)), mm.group(2).lower(), int(mm.group(3))
                dias = list(range(d1, d2 + 1)) if sep == "a" and 0 < d2 - d1 <= 14 else [d1, d2]
                if all(_ok(ano_ctx, mes_ctx, d) for d in dias):
                    for d in reversed(dias):
                        fila.appendleft(f"{d:02d} - {mm.group(4)}")
                    continue
        data, span = _achar_data(l, ano_ctx)
        if data is None and mes_ctx:
            m = _DIA.match(l)
            if m and _ok(ano_ctx, mes_ctx, int(m.group(1))):
                data, span = (ano_ctx, mes_ctx, int(m.group(1))), m.span()
        if span:
            pre = re.sub(rf"(?i)\b{DIAS}\b[\s,.\-–—]*$", "", l[:span[0]])
            pos = re.sub(rf"(?i)^[\s,.\-–—(]*\b{DIAS}\b\)?", "", l[span[1]:])
            resto = pre + " " + pos
        else:
            resto = l
        hora = None
        for m in _HORA.finditer(resto):
            h = int(m.group(1) or m.group(3))
            mi = int(m.group(2) or 0)
            if h <= 23 and mi <= 59:
                hora = (h, mi)
                resto = resto[:m.start()] + " " + resto[m.end():]
                break
        local = ""
        if "@" in resto:
            resto, local = resto.split("@", 1)
            local = local.strip(" -–—|:;,.")
        resto = re.sub(r"\bàs\b", " ", resto)
        resto = re.sub(r"\(\s*\)", " ", resto)
        titulo = re.sub(r"\s+", " ", resto).strip(" -–—|:;,.·•\t")
        if titulo.count("(") < titulo.count(")"):
            titulo = titulo.rstrip(")").strip()
        elif titulo.count("(") > titulo.count(")"):
            titulo = titulo.lstrip("(").strip()
        erro = "" if data else ("Data inválida" if _NUM.search(l) else "Não encontrei a data")
        if data and not titulo:
            erro = "Sem título"
        itens.append(dict(linha=bruto.strip(), titulo=titulo, data=data, hora=hora, local=local,
                          tipo=tipo_por_titulo(titulo), erro=erro))
    return itens
