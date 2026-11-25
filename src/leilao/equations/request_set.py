"""O que o aluno solicita na linha de base — anteprojeto, eq. (50)."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from ._knapsack import knapsack


def request_set(
    *,
    utilities: Mapping[str, float],
    available: Iterable[str],
    hours: Mapping[str, int],
    capacity: int,
    conflicts: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """`available` é B_a^(t,r), `capacity` é W_a^(t,r) e `conflicts` mapeia"""
    wanted = set(available)
    items: Sequence[str] = [
        name
        for name in utilities
        if name in wanted and utilities[name] > 0.0
    ]
    if not items:
        return []
    chosen = knapsack(
        items=items,
        values=utilities,
        weights=hours,
        capacity=capacity,
        conflicts=conflicts,
    )
    return sorted(chosen, key=lambda name: -utilities[name])
