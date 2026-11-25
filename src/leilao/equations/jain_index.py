"""Equidade de Jain — anteprojeto, eq. (55)."""
from __future__ import annotations

from collections.abc import Sequence


def jain_index(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    square_sum = sum(value**2 for value in values)
    if square_sum == 0:
        return 0.0
    return min(1.0, sum(values) ** 2 / (len(values) * square_sum))
