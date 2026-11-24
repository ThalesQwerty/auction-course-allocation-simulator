"""A mochila 0-1 sobre a carga horária, com grafo de conflito opcional.

    K = argmax { Σ_{x ∈ K} u_{a,x} : K ⊆ itens,
                 Σ_{x ∈ K} w_x ≤ W,
                 |K ∩ X| ≤ 1 ∀ X ∈ E }

Duas equações do modelo são esta mesma mochila sobre conjuntos diferentes, e
por isso a tabela mora aqui: `equations.request_set` a resolve sobre o que é
**elegível**, antes da alocação (eq. 50), e `equations.retained_set` sobre o
que foi **conquistado**, depois dela. Valor e peso são os mesmos nas duas —
utilidade e carga horária —, e o que muda é de onde vêm os itens, qual teto os
limita e se há conflito a respeitar: o pedido escolhe entre turmas que se
excluem (`E = M ∪ G`), e o que o aluno leva já veio sem choque da alocação.

Resolvida por programação dinâmica, não por PLI: a instância é de um aluno só,
com dezenas de itens e uma capacidade em horas, e a tabela é muito mais barata
que uma chamada ao CBC — que aqui seria feita uma vez por aluno, por rodada,
por período.

Dois cortes a mantêm pequena. Se tudo cabe e nada conflita, não há escolha a
fazer. E, como os pesos são inteiros, dividir todos eles e a capacidade pelo
MDC dá exatamente o mesmo ótimo numa tabela MDC vezes menor — uma grade de 60
e 90 h encolhe a capacidade de 450 para 15.

NÃO DEGENERA NUMA ORDENAÇÃO
---------------------------

A heurística natural seria tomar da maior utilidade para a menor até encher, e
ela erra assim que as cargas diferem. Com teto de 122 h e as candidatas
Algoritmos (90 h, u 0,22), Cálculo (60 h, 0,13) e Física (60 h, 0,11): a
ordenação toma Algoritmos e para, com 0,22; a mochila toma Cálculo + Física,
120 h e 0,24. A ordenação sacrifica duas disciplinas baratas para salvar uma
cara.

O CONFLITO É FILTRO, E O ÓTIMO VIRA APROXIMADO
-----------------------------------------------

Cada célula guarda, além da utilidade e das posições escolhidas, os cliques
que esse subconjunto já ocupa — um inteiro, um bit por clique. Um item só
estende a célula se não colidir com ela, de modo que **toda** célula é viável
por construção.

O preço é que a subestrutura ótima deixa de valer: a célula de onde se
estenderia pode ser a de maior utilidade e, ainda assim, a errada, porque uma
pior e sem o clique ocupado chegaria mais longe. A resposta é um ótimo local,
e sem conflito nenhum (`conflicts=None`) a tabela volta a ser a mochila 0-1
exata.

É a aproximação certa para o lugar: a mochila do pedido é a auto-restrição
*ex-ante* do aluno, que o trabalho descreve como **otimização local
heurística sob incerteza** — não a alocação da universidade, que é exata e
roda na PLI. Resolver o conflito exatamente custaria 2^|E| estados por célula,
uma vez por aluno, por rodada, por período.

ORDEM DE DESEMPATE
------------------

Entre subconjuntos de utilidade igual ganha o que contém o item **listado
primeiro** — a ordem de `items`, que é a ordem da grade no cenário. O
desempate compara as posições escolhidas lexicograficamente: índice mais baixo
vence, e nunca é a chave de ordenação.

Com interesse sorteado o empate tem probabilidade zero. A regra existe para
que um cenário escrito à mão não dependa da ordem de iteração, que é a mesma
exigência de determinismo da Seção 7.3.

Item de carga nula não consome o teto, então entra sempre e nem chega à tabela
— havendo conflito entre dois deles, entra o primeiro da grade. Carga nula não
existe no simulador (`Discipline.hours > 0` é validado): é guarda, não regra.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import gcd


def knapsack(
    *,
    items: Sequence[str],
    values: Mapping[str, float],
    weights: Mapping[str, int],
    capacity: int,
    conflicts: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """O subconjunto, devolvido **na ordem de `items`**.

    `conflicts` mapeia cada item nos cliques de `E` a que ele pertence; itens
    que compartilham um clique não saem juntos. Sem ele não há conflito e a
    resposta é o ótimo exato.

    Item ausente de `values` entra com valor nulo: ele não é escolhido a menos
    que caiba de graça. Quem reordena por preferência é quem chama.
    """
    if capacity < 0:
        raise ValueError("a capacidade da mochila não pode ser negativa")

    # Um bit por clique, atribuído na ordem em que o clique aparece: o teste de
    # conflito vira um `and` de inteiros, e o conjunto ocupado, um `or`.
    bit_of_clique: dict[str, int] = {}
    cliques: dict[str, int] = {}
    for name in items:
        mask = 0
        for clique in (conflicts or {}).get(name, ()):
            mask |= bit_of_clique.setdefault(clique, 1 << len(bit_of_clique))
        cliques[name] = mask

    taken = 0
    kept: set[str] = set()
    for name in items:
        if weights[name] <= 0 and not taken & cliques[name]:
            kept.add(name)
            taken |= cliques[name]

    pool = [name for name in items if 0 < weights[name] <= capacity]
    crowded = taken
    for name in pool:
        if crowded & cliques[name]:
            break
        crowded |= cliques[name]
    else:
        if sum(weights[name] for name in pool) <= capacity:
            kept.update(pool)
            return [name for name in items if name in kept]

    unit = 0
    for name in pool:
        unit = gcd(unit, weights[name])
    scaled = {name: weights[name] // unit for name in pool}
    room = capacity // unit

    # dp[c] = (utilidade acumulada, posições escolhidas, cliques ocupados) com
    # peso total ≤ c. A varredura de trás para frente é o que torna a tabela
    # 0-1 num vetor só: `dp[c - peso]` ainda é o estado de antes deste item.
    dp: list[tuple[float, tuple[int, ...], int]] = [
        (0.0, (), taken) for _ in range(room + 1)
    ]
    for index, name in enumerate(pool):
        weight, value, clique = scaled[name], values.get(name, 0.0), cliques[name]
        for c in range(room, weight - 1, -1):
            carried, chosen, occupied = dp[c - weight]
            if occupied & clique:
                continue
            candidate = (carried + value, chosen + (index,), occupied | clique)
            if _wins(candidate, dp[c]):
                dp[c] = candidate

    # A varredura final existe por causa do filtro: sem conflito `dp[room]` é o
    # melhor de todos, mas o filtro pode ter deixado numa célula mais apertada
    # um subconjunto que nunca chegou ao topo.
    best = dp[0]
    for cell in dp[1:]:
        if _wins(cell, best):
            best = cell

    kept.update(pool[index] for index in best[1])
    return [name for name in items if name in kept]


def _wins(
    candidate: tuple[float, tuple[int, ...], int],
    current: tuple[float, tuple[int, ...], int],
) -> bool:
    """Mais utilidade vence; empatada, vence o índice mais baixo."""
    return candidate[0] > current[0] or (
        candidate[0] == current[0] and candidate[1] < current[1]
    )
