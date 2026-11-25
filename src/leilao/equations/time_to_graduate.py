"""Tempo de formatura: períodos do ingresso ao diploma."""
from __future__ import annotations

from collections.abc import Iterable


def time_to_graduate(spans: Iterable[int]) -> float | None:
    values = list(spans)
    return sum(values) / len(values) if values else None
