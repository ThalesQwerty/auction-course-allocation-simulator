"""Rodada média: em que rodada a demanda do período foi atendida."""
from __future__ import annotations

from collections.abc import Sequence


def mean_round(*, allocations_per_round: Sequence[int]) -> float | None:
    """`allocations_per_round[i]` é o que a rodada `i + 1` concedeu."""
    total = sum(allocations_per_round)
    if total <= 0:
        return None
    weighted = sum(
        (index + 1) * count for index, count in enumerate(allocations_per_round)
    )
    return weighted / total
