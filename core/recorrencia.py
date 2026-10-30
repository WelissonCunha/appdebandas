"""Gera as datas de uma regra como 'toda quinta' ou 'o 2º sábado do mês'."""
from datetime import timedelta

DIAS_SEL = [(0, "Segunda-feira"), (1, "Terça-feira"), (2, "Quarta-feira"), (3, "Quinta-feira"), (4, "Sexta-feira"),
            (5, "Sábado"), (6, "Domingo")]
DIAS_ABREV = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
FREQS = [("todas", "Toda semana"), ("1", "1º do mês"), ("2", "2º do mês"), ("3", "3º do mês"), ("4", "4º do mês"),
         ("ultimo", "Último do mês")]


def datas_regra(inicio, fim, dia_semana, freq):
    """Todas as datas entre inicio e fim (inclusive) que caem em dia_semana (0=segunda) e na frequência."""
    d = inicio + timedelta(days=(dia_semana - inicio.weekday()) % 7)
    saida = []
    while d <= fim:
        if freq == "todas":
            ok = True
        elif freq == "ultimo":
            ok = (d + timedelta(days=7)).month != d.month
        else:
            ok = (d.day - 1) // 7 + 1 == int(freq)
        if ok:
            saida.append(d)
        d += timedelta(days=7)
    return saida
