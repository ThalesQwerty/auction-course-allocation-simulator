"""Como as notas de primeira tentativa se distribuem."""
from __future__ import annotations

from collections.abc import Sequence

BINS = 10
TOP = 10.0


def grade_histogram(grades: Sequence[float], bins: int = BINS) -> list[float]:
    if not grades:
        return [0.0] * bins
    counts = [0] * bins
    for grade in grades:
        counts[min(bins - 1, max(0, int(grade / TOP * bins)))] += 1
    return [count / len(grades) for count in counts]
