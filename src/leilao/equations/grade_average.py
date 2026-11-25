"""Coeficiente de rendimento do aluno — anteprojeto, eq. (49)."""
from __future__ import annotations

from collections.abc import Set


def grade_average(
    *, taken: Set[str], grades: dict[str, float], hours: dict[str, int]
) -> float:
    if not taken:
        return 0.0
    total_hours = sum(hours[name] for name in taken)
    weighted = sum(hours[name] * grades.get(name, 0.0) for name in taken)
    return weighted / total_hours
