"""Como uma simulação inteira vira um número por métrica."""
from __future__ import annotations

from collections.abc import Sequence


def weighted_mean(pairs: Sequence[tuple[float, int]]) -> float | None:
    total = sum(weight for _, weight in pairs)
    if not total:
        return None
    return sum(value * weight for value, weight in pairs) / total
