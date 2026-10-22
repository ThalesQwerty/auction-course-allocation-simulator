"""Resolvedor exato do Problema de Determinação de Vencedores (WDP) via PLI.

Implementa a função resolvedora abstrata O(P) = z_max (eq. 10), maximizando a
preferência agregada dos bens alocados:

    max  Z = sum_{(a,x) in D} p_{a,x} * z_{a,x}                       (eq. 8)

sujeito a:

    sum_{a in A} z_{a,x} <= q_x                    forall x in B      (eq. 3)
    sum_{x in B} z_{a,x} * w_x <= W_a              forall a in A      (eq. 4)
    sum_{x in Y} z_{a,x} <= 1        forall a in A, forall Y in X     (eq. 5)
    z_{a,x} in {0, 1}                              forall (a,x) in D  (eq. 1)

O problema é uma extensão do 0-1 Multiple Knapsack Problem with Shared Items
and Conflict Graphs (NP-difícil), conforme discutido na Seção 3.1 e 6.2 do
anteprojeto. Para instâncias pequenas/moderadas, o solver CBC (embutido no
PuLP) resolve rapidamente devido à esparsidade natural do problema (Seção 6.3).
"""
from __future__ import annotations

import pulp

from .entities import Allocation, Problem


class InfeasibleOrUnsolvedError(RuntimeError):
    """Levantado quando o solver não encontra uma solução ótima comprovada."""


def solve_wdp(problem: Problem, *, msg: bool = False) -> Allocation:
    """Resolve o WDP para o problema P e retorna a matriz ótima de decisões z_max.

    Retorna apenas as entradas (a, x) in D; pares fora de D são 0 por
    definição (eq. 2) e não aparecem no dicionário retornado.
    """
    if not problem.demands:
        return {}

    lp = pulp.LpProblem("WDP", pulp.LpMaximize)

    # Variáveis nomeadas por índice, e não pelos ids: ids de domínio podem
    # conter espaços e acentos (ex.: "Cálculo I"), que não sobrevivem ao
    # formato LP lido pelo CBC.
    z: dict[tuple[str, str], pulp.LpVariable] = {
        (d.agent_id, d.good_id): pulp.LpVariable(f"z_{i}", cat="Binary")
        for i, d in enumerate(problem.demands)
    }

    # Função objetivo — eq. (8)
    lp += pulp.lpSum(d.preference * z[(d.agent_id, d.good_id)] for d in problem.demands)

    vars_by_good: dict[str, list[pulp.LpVariable]] = {}
    vars_by_agent: dict[str, list[tuple[str, pulp.LpVariable]]] = {}
    for d in problem.demands:
        var = z[(d.agent_id, d.good_id)]
        vars_by_good.setdefault(d.good_id, []).append(var)
        vars_by_agent.setdefault(d.agent_id, []).append((d.good_id, var))

    # Restrição de disponibilidade dos bens — eq. (3)
    for i, good in enumerate(problem.goods):
        vars_for_good = vars_by_good.get(good.id)
        if vars_for_good:
            lp += pulp.lpSum(vars_for_good) <= good.quantity, f"quantity_{i}"

    # Restrição de capacidade dos agentes — eq. (4)
    weight_by_good = {g.id: g.weight for g in problem.goods}
    for i, agent in enumerate(problem.agents):
        terms = [
            weight_by_good[good_id] * var for good_id, var in vars_by_agent.get(agent.id, [])
        ]
        if terms:
            lp += pulp.lpSum(terms) <= agent.capacity, f"capacity_{i}"

    # Restrição de exclusão mútua — eq. (5)
    for i, agent in enumerate(problem.agents):
        for j, excl in enumerate(problem.exclusions):
            vars_in_clique = [
                z[(agent.id, good_id)]
                for good_id in excl.goods
                if (agent.id, good_id) in z
            ]
            if len(vars_in_clique) > 1:
                lp += pulp.lpSum(vars_in_clique) <= 1, f"exclusion_{i}_{j}"

    status = lp.solve(pulp.PULP_CBC_CMD(msg=msg))
    status_name = pulp.LpStatus[status]
    if status_name != "Optimal":
        raise InfeasibleOrUnsolvedError(f"WDP solver returned status {status_name!r}")

    return {key: int(round(var.value())) for key, var in z.items()}


def solve_wdp_greedy(problem: Problem, *, msg: bool = False) -> Allocation:
    """A varredura gulosa: atende as demandas em ordem decrescente de
    preferência, concedendo enquanto houver vaga, carga e exclusão livre.

    Mesma assinatura e mesmo retorno de `solve_wdp`, de propósito — é o que
    torna o eixo **ordenação × PLI** um eixo de verdade: o lance, o preço de 2º
    preço (eq. 24) e o consumo (eq. 27) são calculados do mesmo jeito dos dois
    lados, e a única coisa que muda é quem decide a alocação.

    Com lance como preferência, isto **é** o mecanismo de *bidding points* dos
    business schools: o aluno reparte pontos, os lances são processados em
    ordem decrescente, e cada um é atendido se a disciplina tem vaga e a grade
    do aluno ainda comporta. A restrição de carga não volta a ser resolvida
    pelo aluno em casa — ela é resolvida aqui, ex-post, como na PLI.

    O guloso é **ótimo da relaxação sem a restrição de carga**: sem ela o
    problema se separa por bem, e tomar os q_x maiores lances de cada um é
    exatamente o que esta varredura faz. Os dois resolvedores só divergem,
    portanto, onde a carga aperta — e é por isso que o eixo só tem conteúdo em
    cenário com conjunto elegível maior que W_a.
    """
    if not problem.demands:
        return {}

    quantity = {g.id: g.quantity for g in problem.goods}
    weight = {g.id: g.weight for g in problem.goods}
    room = {a.id: a.capacity for a in problem.agents}
    # Cliques de exclusão mútua (eq. 5): no máximo um bem de cada clique por
    # agente. O guloso respeita olhando o que já concedeu.
    taken: dict[str, set[str]] = {a.id: set() for a in problem.agents}

    allocation: Allocation = {(d.agent_id, d.good_id): 0 for d in problem.demands}
    for demand in sorted(
        problem.demands, key=lambda d: (-d.preference, d.agent_id, d.good_id)
    ):
        good_id, agent_id = demand.good_id, demand.agent_id
        if quantity.get(good_id, 0) <= 0:
            continue
        if room.get(agent_id, 0) < weight.get(good_id, 0):
            continue
        if any(
            good_id in exclusion.goods and taken[agent_id] & set(exclusion.goods)
            for exclusion in problem.exclusions
        ):
            continue
        quantity[good_id] -= 1
        room[agent_id] -= weight[good_id]
        taken[agent_id].add(good_id)
        allocation[(agent_id, good_id)] = 1
    return allocation
