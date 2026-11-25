"""O conjunto em que o aluno ainda pode obter vaga nesta rodada — anteprojeto, eq. (15).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence, Set


def available_goods(
    *,
    eligible: Iterable[str],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: float,
    already_won: Set[str],
    conflicts: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    taken: set[str] = set()
    for name in already_won:
        taken.update(conflicts[name] if conflicts else (name,))
    return [
        name
        for name in eligible
        if seats[name] > 0
        and hours[name] <= capacity
        and taken.isdisjoint(conflicts[name] if conflicts else (name,))
    ]
