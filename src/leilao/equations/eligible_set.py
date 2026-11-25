"""O conjunto elegível do aluno no período — anteprojeto, eq. (42)."""
from __future__ import annotations

from collections.abc import Sequence, Set


def eligible_set(
    *,
    names: Sequence[str],
    approved: Set[str],
    prerequisites: dict[str, tuple[str, ...]],
    elective_hours_by_discipline: dict[str, int],
    elective_hours_needed: int,
) -> list[str]:
    earned = sum(
        hours
        for name, hours in elective_hours_by_discipline.items()
        if name in approved
    )
    quota_met = earned >= elective_hours_needed
    return [
        name
        for name in names
        if name not in approved
        and all(p in approved for p in prerequisites[name])
        and not (name in elective_hours_by_discipline and quota_met)
    ]
