"""Distribui pessoas nas funções de um modelo de escala, com rodízio justo."""


def distribuir(eventos, funcoes, indisponiveis):
    """
    eventos: [(evento_id, data)] em ordem cronológica
    funcoes: [(nome_da_funcao, [membro_id, ...])]  (1 pessoa = fixa; várias = rodízio)
    indisponiveis: {(membro_id, data)}
    Devolve {evento_id: [(funcao, membro_id | None, motivo | None)]}.
    Quem não pôde ser escalado (indisponível ou já escalado no mesmo evento) continua primeiro da fila.
    """
    filas = [list(pool) for _, pool in funcoes]
    resultado = {}
    for ev_id, dia in eventos:
        usados, linhas = set(), []
        for i, (nome, _) in enumerate(funcoes):
            fila, escolhido, motivo = filas[i], None, None
            if not fila:
                motivo = "ninguém no modelo"
            for cand in fila:
                if cand in usados or (cand, dia) in indisponiveis:
                    continue
                escolhido = cand
                fila.remove(cand)
                fila.append(cand)
                break
            if escolhido is None and fila:
                motivo = "todos indisponíveis ou já escalados"
            if escolhido is not None:
                usados.add(escolhido)
            linhas.append((nome, escolhido, motivo))
        resultado[ev_id] = linhas
    return resultado
