"""Resolvedor do Problema de Determinação de Vencedores (WDP)."""
from __future__ import annotations

import pulp

from .entities import Allocation, Demand, Problem

INTEGER_INCREMENT = 0.99


class InfeasibleOrUnsolvedError(RuntimeError):
    """Levantado quando o solver não encontra solução ótima comprovada."""


def _model(problem: Problem) -> tuple[pulp.LpProblem, dict[tuple[str, str], pulp.LpVariable]]:
    """As restrições (3), (4) e (5) — as mesmas em qualquer objetivo."""
    lp = pulp.LpProblem("WDP", pulp.LpMaximize)

    variables = {
        (d.agent_id, d.good_id): pulp.LpVariable(f"z_{i}", cat="Binary")
        for i, d in enumerate(problem.demands)
    }

    by_good: dict[str, list[pulp.LpVariable]] = {}
    by_agent: dict[str, list[tuple[str, pulp.LpVariable]]] = {}
    for demand in problem.demands:
        variable = variables[(demand.agent_id, demand.good_id)]
        by_good.setdefault(demand.good_id, []).append(variable)
        by_agent.setdefault(demand.agent_id, []).append((demand.good_id, variable))

    for i, good in enumerate(problem.goods):
        if by_good.get(good.id):
            lp += pulp.lpSum(by_good[good.id]) <= good.quantity, f"quantity_{i}"

    weight = {g.id: g.weight for g in problem.goods}
    for i, agent in enumerate(problem.agents):
        terms = [weight[gid] * var for gid, var in by_agent.get(agent.id, [])]
        if terms:
            lp += pulp.lpSum(terms) <= agent.capacity, f"capacity_{i}"

    for i, agent in enumerate(problem.agents):
        for j, exclusion in enumerate(problem.exclusions):
            clique = [
                variables[(agent.id, good_id)]
                for good_id in exclusion.goods
                if (agent.id, good_id) in variables
            ]
            if len(clique) > 1:
                lp += pulp.lpSum(clique) <= 1, f"exclusion_{i}_{j}"

    return lp, variables


def _increment(problem: Problem) -> float | None:
    """O passo mínimo do objetivo, quando dá para afirmar um — ver `INTEGER_INCREMENT`."""
    if all(float(d.preference).is_integer() for d in problem.demands):
        return INTEGER_INCREMENT
    return None


def _solve(lp: pulp.LpProblem, *, msg: bool, increment: float | None) -> None:
    options = [] if increment is None else [f"increment {increment}"]
    status = pulp.LpStatus[lp.solve(pulp.PULP_CBC_CMD(msg=msg, options=options))]
    if status != "Optimal":
        raise InfeasibleOrUnsolvedError(f"WDP solver returned status {status!r}")


def _taken(
    variables: dict[tuple[str, str], pulp.LpVariable]
) -> dict[tuple[str, str], int]:
    return {key: int(round(var.value())) for key, var in variables.items()}


def solve_wdp(problem: Problem, *, msg: bool = False) -> Allocation:
    """z_max por PLI — eq. (10)."""
    if not problem.demands:
        return {}

    lp, variables = _model(problem)
    lp.setObjective(
        pulp.lpSum(
            d.preference * variables[(d.agent_id, d.good_id)] for d in problem.demands
        )
    )
    _solve(lp, msg=msg, increment=_increment(problem))
    return _taken(variables)


