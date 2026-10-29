"""A varredura gulosa por preferência decrescente — o resolvedor alternativo.

    para (a, x) em ordem decrescente de p_{a,x}:
        se q_x > 0 e w_x ≤ W_a e nenhum conflito:  z_{a,x} = 1

Mesma assinatura e mesmo retorno do resolvedor exato, de propósito — é o que
torna o eixo **ordenação × PLI** um eixo de verdade: a preferência da eq.
(22), o preço da eq. (24) e o consumo da eq. (25) são calculados do mesmo
jeito dos dois lados, e a única coisa que muda é quem decide a alocação.

Com lance como preferência, isto **é** o mecanismo de *bidding points* dos
business schools: o aluno reparte pontos, os lances são processados em ordem
decrescente, e cada um é atendido se a disciplina tem vaga e a grade do aluno
ainda comporta. A restrição de carga não volta a ser resolvida pelo aluno em
casa — ela é resolvida aqui, *ex-post*, como na PLI.

**O guloso é ótimo da relaxação sem a restrição de carga**: sem ela o
problema se separa por bem, e tomar os q_x maiores lances de cada um é
exatamente o que esta varredura faz. Os dois resolvedores só divergem,
portanto, onde a carga aperta — e é por isso que o eixo só tem conteúdo em
cenário com conjunto elegível maior que W_a.

O desempate `(-p, agente, bem)` deixa a varredura determinística mesmo com
preferências iguais, embora a perturbação já torne o empate improvável.
"""
from __future__ import annotations

from collections.abc import Sequence


def greedy_allocation(
    *,
    demands: Sequence[tuple[str, str, float]],
    seats: dict[str, int],
    hours: dict[str, float],
    capacity: dict[str, float],
    exclusions: Sequence[frozenset[str]] = (),
) -> dict[tuple[str, str], int]:
    remaining = dict(seats)
    room = dict(capacity)
    # Cliques de exclusão mútua (eq. 5): no máximo um bem de cada clique por
    # agente. O guloso respeita olhando o que já concedeu.
    taken: dict[str, set[str]] = {agent_id: set() for agent_id in capacity}

    allocation = {(agent_id, good_id): 0 for agent_id, good_id, _ in demands}
    for agent_id, good_id, _preference in sorted(
        demands, key=lambda d: (-d[2], d[0], d[1])
    ):
        if remaining.get(good_id, 0) <= 0:
            continue
        if room.get(agent_id, 0) < hours.get(good_id, 0):
            continue
        if any(
            good_id in clique and taken[agent_id] & clique for clique in exclusions
        ):
            continue
        remaining[good_id] -= 1
        room[agent_id] -= hours[good_id]
        taken[agent_id].add(good_id)
        allocation[(agent_id, good_id)] = 1
    return allocation
