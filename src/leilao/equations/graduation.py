"""Conclusão de curso, estendida pelas optativas — anteprojeto, eq. (40)."""
from __future__ import annotations

from collections.abc import Set


def has_graduated(
    *,
    approved: Set[str],
    required: Set[str],
    elective_hours_by_discipline: dict[str, int],
    elective_hours_needed: int,
) -> bool:
    if not required <= approved:
        return False
    earned = sum(
        hours
        for name, hours in elective_hours_by_discipline.items()
        if name in approved
    )
    return earned >= elective_hours_needed
