"""Lê PDFs de calendário com os eventos listados abaixo de cada mês e devolve texto no formato do importador."""
import re
from statistics import median

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
         "Novembro", "Dezembro"]
_INICIO = re.compile(r"^\d{1,2}(?:\s*(?:e|a|,)\s*\d{1,2})?\s*[-–—]\s*\S")


def _linhas(palavras):
    """Agrupa palavras na mesma altura em linhas: [(top, texto)]."""
    saida, atual, topo = [], [], None
    for w in sorted(palavras, key=lambda w: (round(w["top"], 1), w["x0"])):
        if topo is None or abs(w["top"] - topo) > 2.5:
            if atual:
                saida.append((topo, " ".join(x["text"] for x in sorted(atual, key=lambda x: x["x0"]))))
            atual, topo = [], w["top"]
        atual.append(w)
    if atual:
        saida.append((topo, " ".join(x["text"] for x in sorted(atual, key=lambda x: x["x0"]))))
    return saida


def _pagina_em_colunas(p):
    """Devolve [(mes, [eventos])] ou None se a página não tem o layout 'meses com listas abaixo'."""
    ws = p.extract_words(extra_attrs=["size"])
    cab = []
    for w in ws:
        if w["text"] in MESES and not any(abs(o["top"] - w["top"]) <= 2 and o["text"] not in MESES and o is not w for o in ws
                                          if abs(o["x0"] - w["x0"]) < 120):
            cab.append(w)
    if not cab:
        return None
    tam = median(w["size"] for w in cab)
    # linhas de meses (por altura)
    cab.sort(key=lambda w: (w["top"], w["x0"]))
    linhas_cab, atual = [], [cab[0]]
    for w in cab[1:]:
        if abs(w["top"] - atual[0]["top"]) <= 5:
            atual.append(w)
        else:
            linhas_cab.append(sorted(atual, key=lambda x: x["x0"]))
            atual = [w]
    linhas_cab.append(sorted(atual, key=lambda x: x["x0"]))
    # colunas = onde começam as linhas de evento
    inicios = []
    for a, b in zip(ws, ws[1:]):
        if (re.fullmatch(r"\d{1,2}", a["text"]) and b["text"] in ("-", "e") and abs(a["top"] - b["top"]) < 2
                and b["x0"] - a["x1"] < 6 and a["size"] < tam + 1.5):
            inicios.append(a["x0"])
    if not inicios:
        return None
    inicios.sort()
    colunas = [[inicios[0]]]
    for x in inicios[1:]:
        if x - colunas[-1][-1] <= 25:
            colunas[-1].append(x)
        else:
            colunas.append([x])
    lefts = [median(c) for c in colunas]
    n_meses = max(len(l) for l in linhas_cab)
    if len(lefts) != n_meses or any(len(l) != n_meses for l in linhas_cab):
        return None
    larg = median([b - a for a, b in zip(lefts, lefts[1:])]) if len(lefts) > 1 else 140
    limite = lefts[-1] + larg * 0.9
    tops = [l[0]["top"] - 3 for l in linhas_cab] + [1e9]
    grupos = {}
    for w in ws:
        if w["x0"] < lefts[0] - 12 or w["x0"] >= limite or w["top"] < tops[0]:
            continue
        r = max(i for i in range(len(linhas_cab)) if w["top"] >= tops[i])
        c = max(i for i in range(len(lefts)) if w["x0"] >= lefts[i] - 12)
        grupos.setdefault((r, c), []).append(w)
    saida = []
    for r, linha in enumerate(linhas_cab):
        for c, cabec in enumerate(linha):
            eventos, ultimo_top = [], None
            for top, txt in _linhas(grupos.get((r, c), [])):
                if _INICIO.match(txt):
                    eventos.append(txt)
                elif eventos and ultimo_top is not None and top - ultimo_top <= 14:
                    eventos[-1] += " " + txt
                else:
                    continue
                ultimo_top = top
            saida.append((cabec["text"], eventos))
    return saida


def extrair_texto_pdf(arquivo):
    """Texto no formato 'Mês' + linhas 'DD - título', pronto para o importador."""
    import pdfplumber
    partes, ano = [], None
    with pdfplumber.open(arquivo) as pdf:
        if len(pdf.pages) > 30:
            raise ValueError("O PDF tem páginas demais (máximo 30).")
        for i, p in enumerate(pdf.pages):
            if i == 0:
                topo = " ".join(w["text"] for w in p.extract_words() if w["top"] < 90)
                m = re.search(r"\b(20\d{2})\b", topo)
                ano = m.group(1) if m else None
            blocos = _pagina_em_colunas(p)
            if blocos is None:  # layout diferente: usa o texto corrido da página
                partes.append(p.extract_text() or "")
                continue
            for mes, eventos in blocos:
                if eventos:
                    partes.append(f"{mes} {ano}" if ano else mes)
                    partes.extend(eventos)
    return "\n".join(partes)
