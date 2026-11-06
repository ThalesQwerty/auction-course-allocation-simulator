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

**O guloso é ótimo** porque todos os pesos são 1 e o ganho marginal cai
dentro de cada disciplina: basta tomar os maiores ganhos marginais, que é o
que a fila de prioridade faz. Não há tabela de programação dinâmica a montar.

O CRITÉRIO DE PARADA
--------------------

O aluno **não gasta necessariamente tudo**. Ele para quando o ganho marginal
do próximo crédito cai abaixo do limiar da seletividade
(`equations.reserve_threshold`), e o que sobra fica no saldo — disponível nas
rodadas seguintes do período e, com `credit_memory = "carry"`, no período
seguinte.

O `break` é correto porque a comparação é contra a **própria chave do heap**:
se o topo não passa do limiar, nada passa. Uma versão anterior comparava o
ganho marginal contra a utilidade crua enquanto a fila ordenava por score —
a sequência não era monótona no critério, e parar na primeira reprovada
excluía disciplinas que ainda passariam. Com score dos dois lados o problema
não existe.

**Onde a sobra aparece.** Não diluída ao longo das rodadas: a mochila é
chamada nova a cada rodada e o ganho marginal reseta, então o aluno volta a
gastar enquanto houver algo acima do limiar. A sobra materializa quando o
conjunto **disponível** inteiro cai abaixo dele — tipicamente no fim do
período, quando só resta o que ele cortaria.

**Empate vai para a disciplina listada primeiro** — a ordem de `scores`, que
é a ordem da grade no cenário. O posto entra como segundo campo da fila e
resolve qualquer empate, inclusive o de ganhos marginais que coincidem vindos
de scores diferentes (`s_x/2 = s_y/1`). Como o posto é único, a comparação
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
        gain, _rank, name, credits_here = frontier[0]
        if -gain < reserve:
            break
        heapq.heappop(frontier)
        bids[name] = bids.get(name, 0) + 1
        following = credits_here + 1
        heapq.heappush(frontier, (-scores[name] / following, rank[name], name, following))
    return bids
