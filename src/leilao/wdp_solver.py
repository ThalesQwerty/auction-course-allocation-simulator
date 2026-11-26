"""Resolvedor do Problema de Determinação de Vencedores (WDP)."""
from __future__ import annotations

from time import perf_counter

import pulp

from .entities import Allocation, Demand, Problem

INTEGER_INCREMENT = 0.99

TIMEOUT_TOLERANCE = 0.9
"""Quanto do limite já basta para chamar de tempo esgotado: o CBC devolve um
pouco antes do limite cheio, e abaixo disso a culpa é de outra coisa."""


class InfeasibleOrUnsolvedError(RuntimeError):
    """Levantado quando o solver não encontra solução ótima comprovada."""


class AllocationTimeout(RuntimeError):
    """O solver esgotou o tempo concedido à alocação sem provar o ótimo.

    É diferente de não ter solução: a instância é resolvível, e o que faltou foi
    tempo. Quem chama decide o que fazer, e a decisão do trabalho é descartar a
    simulação inteira — nunca aproveitar a solução factível que o CBC devolve,
    que é subótima e faria o leilão parecer pior por motivo de computador.
    """


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


def _solve(
    lp: pulp.LpProblem,
    *,
    msg: bool,
    increment: float | None,
    time_limit: float | None,
) -> None:
    """Resolve e recusa o que não for ótimo provado.

    O teste é em `sol_status`, não em `status`: com `timeLimit` o CBC para no
    tempo e o pulp ainda devolve `Optimal`, com a melhor solução que achou. É
    `sol_status` que distingue o ótimo provado (1) do apenas factível (2).
    """
    options = [] if increment is None else [f"increment {increment}"]
    started = perf_counter()
    lp.solve(pulp.PULP_CBC_CMD(msg=msg, options=options, timeLimit=time_limit))
    if lp.sol_status == pulp.LpSolutionOptimal:
        return
    elapsed = perf_counter() - started
    if time_limit is not None and elapsed >= time_limit * TIMEOUT_TOLERANCE:
        raise AllocationTimeout(
            f"alocação não resolvida em {time_limit:g} s"
            f" ({len(lp.variables())} variáveis)"
        )
    raise InfeasibleOrUnsolvedError(
        f"WDP solver returned status {pulp.LpStatus[lp.status]!r}"
    )


def _taken(
    variables: dict[tuple[str, str], pulp.LpVariable]
) -> dict[tuple[str, str], int]:
    return {key: int(round(var.value())) for key, var in variables.items()}


def solve_wdp(
    problem: Problem, *, msg: bool = False, time_limit: float | None = None
) -> Allocation:
    """z_max por PLI — eq. (10). `time_limit` em segundos, nulo sem teto."""
    if not problem.demands:
        return {}

    lp, variables = _model(problem)
    lp.setObjective(
        pulp.lpSum(
            d.preference * variables[(d.agent_id, d.good_id)] for d in problem.demands
        )
    )
    _solve(lp, msg=msg, increment=_increment(problem), time_limit=time_limit)
    return _taken(variables)


