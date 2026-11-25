"""Linha de base: matrícula por ordenação de CR (Seção 7.3.1, eqs. 49-50)."""
from __future__ import annotations

from .behavior import decide
from .entities import Agent, Demand, Good, MutualExclusion, Problem
from .equations import NEUTRAL, Behavior, serial_dictatorship
from .equations import request_set as rank_requests
from .wdp_solver import solve_wdp

__all__ = ["allocate_by_ilp", "allocate_by_ranking", "request_set"]

allocate_by_ranking = serial_dictatorship


def request_set(
    *,
    utilities: dict[str, float],
    available: list[str],
    hours: dict[str, int],
    capacity: int,
    behavior: Behavior = NEUTRAL,
    classes: dict[str, tuple[str, ...]] | None = None,
    conflicts: dict[str, tuple[str, ...]] | None = None,
    interest: float = 0.0,
) -> list[str]:
    """D_a^(t,r) — ver `equations.request_set`."""
    groups, scores, _reserve = decide(
        utilities=utilities, behavior=behavior, classes=classes, interest=interest
    )
    if not classes:
        return rank_requests(
            utilities=groups,
            available=available,
            hours=hours,
            capacity=capacity,
            conflicts=conflicts,
        )

    admitted = {name for discipline in groups for name in classes[discipline]}
    return rank_requests(
        utilities=scores,
        available=[name for name in available if name in admitted],
        hours=hours,
        capacity=capacity,
        conflicts=conflicts
        or {
            name: (discipline,)
            for discipline, names in classes.items()
            for name in names
        },
    )


def allocate_by_ilp(
    *,
    requests: list[tuple[str, str]],
    priority: dict[str, float],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: dict[str, int],
    conflicts: dict[str, tuple[str, ...]] | None = None,
    tiebreak: dict[str, float] | None = None,
) -> list[tuple[str, str]]:
    """A mesma linha de base, resolvida globalmente: maximiza a soma dos CRs"""
    if not requests:
        return []
    cliques: dict[str, set[str]] = {}
    for name in seats:
        for group in (conflicts or {}).get(name, ()):
            cliques.setdefault(group, set()).add(name)
    problem = Problem(
        agents=[Agent(student_id, capacity[student_id]) for student_id in capacity],
        goods=[Good(name, seats[name], hours[name]) for name in seats],
        demands=[
            Demand(
                student_id,
                name,
                priority[student_id],
                (tiebreak or {}).get(student_id, 0.0),
            )
            for student_id, name in requests
        ],
        exclusions=[
            MutualExclusion(frozenset(names))
            for names in cliques.values()
            if len(names) > 1
        ],
    )
    return [key for key, taken in solve_wdp(problem).items() if taken]
