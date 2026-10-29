"""A mochila côncava do lance — substitui as eqs. (44)-(46).

O aluno resolve **em casa** um Problema da Mochila côncava: a capacidade é o
orçamento, cada crédito pesa 1, e o valor de investir o N-ésimo crédito numa
disciplina é

    ganho marginal_x(N) = score_x / N

É a lei da utilidade marginal decrescente — o primeiro crédito numa
disciplina é o que mais compra chance de vaga, e cada um depois dele compra
menos. O valor total de c créditos postos em x é, portanto, `score_x` vezes o
c-ésimo número harmônico.

**Por que ela substitui as eqs. (44)-(46).** Aquelas repartiam o orçamento
proporcionalmente à utilidade, truncavam e distribuíam a sobra em ordem de
preferência. O lance proporcional é o ótimo da relaxação contínua desta
mochila — maximizar Σ u_x·ln(c_x) com Σ c_x fixo dá c_x proporcional a u_x —,
de modo que a mochila é a versão **inteira e exata** do mesmo critério e
resolve sozinha o arredondamento que as eqs. (45)-(46) tratavam à parte.

**O guloso é ótimo** porque todos os pesos são 1 e o ganho marginal cai dentro
de cada disciplina: basta tomar os `budget` maiores ganhos marginais, que é o
que a fila de prioridade faz. Não há tabela de programação dinâmica a montar.

O aluno gasta **todo** o saldo, a menos que a utilidade de reserva o pare:
todo crédito a mais tem ganho positivo, crédito não gasto não passa para o
período seguinte, e guardar para a rodada seguinte também não se sustenta —
lance perdedor não consome crédito (eq. 25), então apostar não custa nada.

**Empate vai para a disciplina listada primeiro** — a ordem de `scores`, que
é a ordem da grade no cenário. O posto entra como segundo campo da fila e
resolve qualquer empate, inclusive o de ganhos marginais que coincidem vindos
de utilidades diferentes (`u_x/2 = u_y/1`). Como o posto é único, a comparação
nunca chega aos campos seguintes.

Toda disciplina presente na saída recebeu ao menos um crédito, então a eq.
(18) — lance nulo não é demanda — vale por construção.
"""
from __future__ import annotations

import heapq
from collections.abc import Iterable


def concave_bids(
    *,
    scores: dict[str, float],
    available: Iterable[str],
    budget: int,
    reserve: float = 0.0,
) -> dict[str, int]:
    wanted = set(available)
    pool = [name for name in scores if name in wanted and scores[name] > 0.0]
    if not pool or budget <= 0:
        return {}

    rank = {name: index for index, name in enumerate(pool)}
    # Negativo porque `heapq` é min-heap: a fronteira guarda o ganho do
    # *próximo* crédito de cada disciplina.
    frontier = [(-scores[name], rank[name], name, 1) for name in pool]
    heapq.heapify(frontier)

    bids: dict[str, int] = {}
    for _ in range(budget):
        gain, _rank, name, credits_here = heapq.heappop(frontier)
        if -gain <= reserve:
            break
        bids[name] = bids.get(name, 0) + 1
        following = credits_here + 1
        heapq.heappush(frontier, (-scores[name] / following, rank[name], name, following))
    return bids
