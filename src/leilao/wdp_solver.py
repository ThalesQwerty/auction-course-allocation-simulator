"""Resolvedores do Problema de Determinação de Vencedores (WDP).

Dois, com a mesma assinatura — é o que faz de "quem decide a alocação" um
eixo da comparação, e não uma diferença de implementação:

- `solve_wdp` é a função resolvedora O(P) = z_max da eq. (10), exata, por PLI;
- `solve_wdp_greedy` é a varredura por preferência decrescente, em
  `equations.greedy_allocation`.

O PLI maximiza a preferência agregada dos bens alocados:

    max  Z = Σ_{(a,x) ∈ D} p_{a,x} · z_{a,x}                        (eq. 8)

sujeito a

    Σ_{a ∈ A} z_{a,x} ≤ q_x              ∀ x ∈ B                    (eq. 3)
    Σ_{x ∈ B} z_{a,x} · w_x ≤ W_a        ∀ a ∈ A                    (eq. 4)
    Σ_{x ∈ Y} z_{a,x} ≤ 1                ∀ a ∈ A, ∀ Y ∈ X           (eq. 5)
    z_{a,x} ∈ {0, 1}                     ∀ (a,x) ∈ D                (eq. 1)

É uma extensão do 0-1 Multiple Knapsack Problem with Shared Items and
Conflict Graphs, NP-difícil (Seções 3.1 e 6.2). Para as instâncias deste
trabalho o CBC resolve rápido pela esparsidade natural do problema
(Seção 6.3).

O objetivo não tem forma pura em `equations/` porque ele é montado
simbolicamente, como expressão do PuLP — não há valor a calcular aqui.
"""
from __future__ import annotations

import pulp

from .entities import Allocation, Problem
from .equations import greedy_allocation


class InfeasibleOrUnsolvedError(RuntimeError):
    """Levantado quando o solver não encontra solução ótima comprovada."""


def solve_wdp(problem: Problem, *, msg: bool = False) -> Allocation:
    """z_max por PLI — eq. (10).

    Retorna apenas as entradas (a, x) ∈ D; pares fora de D são 0 por
    definição (eq. 2) e não aparecem no dicionário.
    """
    if not problem.demands:
        return {}

    lp = pulp.LpProblem("WDP", pulp.LpMaximize)

    # Variáveis nomeadas por índice, e não pelos ids: ids de domínio podem
    # conter espaços e acentos ("Cálculo I"), que não sobrevivem ao formato LP
    # lido pelo CBC.
    z = {
        (d.agent_id, d.good_id): pulp.LpVariable(f"z_{i}", cat="Binary")
        for i, d in enumerate(problem.demands)
    }

    lp += pulp.lpSum(
        d.preference * z[(d.agent_id, d.good_id)] for d in problem.demands
    )

    vars_by_good: dict[str, list[pulp.LpVariable]] = {}
    vars_by_agent: dict[str, list[tuple[str, pulp.LpVariable]]] = {}
    for d in problem.demands:
        var = z[(d.agent_id, d.good_id)]
        vars_by_good.setdefault(d.good_id, []).append(var)
        vars_by_agent.setdefault(d.agent_id, []).append((d.good_id, var))

    for i, good in enumerate(problem.goods):
        if vars_by_good.get(good.id):
            lp += pulp.lpSum(vars_by_good[good.id]) <= good.quantity, f"quantity_{i}"

    weight = {g.id: g.weight for g in problem.goods}
    for i, agent in enumerate(problem.agents):
        terms = [weight[gid] * var for gid, var in vars_by_agent.get(agent.id, [])]
        if terms:
            lp += pulp.lpSum(terms) <= agent.capacity, f"capacity_{i}"

    for i, agent in enumerate(problem.agents):
        for j, exclusion in enumerate(problem.exclusions):
            clique = [
                z[(agent.id, good_id)]
                for good_id in exclusion.goods
                if (agent.id, good_id) in z
            ]
            if len(clique) > 1:
                lp += pulp.lpSum(clique) <= 1, f"exclusion_{i}_{j}"

    status = pulp.LpStatus[lp.solve(pulp.PULP_CBC_CMD(msg=msg))]
    if status != "Optimal":
        raise InfeasibleOrUnsolvedError(f"WDP solver returned status {status!r}")

    return {key: int(round(var.value())) for key, var in z.items()}


def solve_wdp_greedy(problem: Problem, *, msg: bool = False) -> Allocation:
    """A varredura gulosa — ver `equations.greedy_allocation`."""
    if not problem.demands:
        return {}
    return greedy_allocation(
        demands=[(d.agent_id, d.good_id, d.preference) for d in problem.demands],
        seats={g.id: g.quantity for g in problem.goods},
        hours={g.id: g.weight for g in problem.goods},
        capacity={a.id: a.capacity for a in problem.agents},
        exclusions=[e.goods for e in problem.exclusions],
    )
