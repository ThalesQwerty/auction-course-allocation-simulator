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

    z: dict[tuple[str, str], pulp.LpVariable] = {
        (d.agent_id, d.good_id): pulp.LpVariable(
            f"z_{d.agent_id}_{d.good_id}", cat="Binary"
        )
        for d in problem.demands
    }

    # Função objetivo — eq. (8)
    lp += pulp.lpSum(d.preference * z[(d.agent_id, d.good_id)] for d in problem.demands)

    # Restrição de disponibilidade dos bens — eq. (3)
    for good in problem.goods:
        vars_for_good = [
            z[(d.agent_id, d.good_id)]
            for d in problem.demands
            if d.good_id == good.id
        ]
        if vars_for_good:
            lp += pulp.lpSum(vars_for_good) <= good.quantity, f"quantity_{good.id}"

    # Restrição de capacidade dos agentes — eq. (4)
    weight_by_good = {g.id: g.weight for g in problem.goods}
    for agent in problem.agents:
        terms = [
            weight_by_good[d.good_id] * z[(d.agent_id, d.good_id)]
            for d in problem.demands
            if d.agent_id == agent.id
        ]
        if terms:
            lp += pulp.lpSum(terms) <= agent.capacity, f"capacity_{agent.id}"

    # Restrição de exclusão mútua — eq. (5)
    for agent in problem.agents:
        for i, excl in enumerate(problem.exclusions):
            vars_in_clique = [
                z[(agent.id, good_id)]
                for good_id in excl.goods
                if (agent.id, good_id) in z
            ]
            if len(vars_in_clique) > 1:
                lp += (
                    pulp.lpSum(vars_in_clique) <= 1,
                    f"exclusion_{agent.id}_{i}",
                )

    status = lp.solve(pulp.PULP_CBC_CMD(msg=msg))
    status_name = pulp.LpStatus[status]
    if status_name != "Optimal":
        raise InfeasibleOrUnsolvedError(f"WDP solver returned status {status_name!r}")

    return {key: int(round(var.value())) for key, var in z.items()}
