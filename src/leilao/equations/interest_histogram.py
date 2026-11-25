"""Como o interesse se reparte dentro da linha de um aluno."""
from __future__ import annotations

from collections.abc import Iterable

BINS = 10


def interest_histogram(
    rows: Iterable[dict[str, float]], bins: int = BINS
) -> list[float]:
    counts = [0] * bins
    total = 0
    for row in rows:
        values = [value for value in row.values() if value > 0]
        if len(values) < 2:
            continue
        low, high = min(values), max(values)
        span = high - low
        for value in values:
            index = (
                bins - 1 if span <= 0 else min(bins - 1, int((value - low) / span * bins))
            )
            counts[index] += 1
        total += len(values)
    if not total:
        return [0.0] * bins
    return [count / total for count in counts]
