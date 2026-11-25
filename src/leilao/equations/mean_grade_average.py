"""CR médio de um recorte — anteprojeto, eq. (56)."""
from __future__ import annotations

from collections.abc import Sequence

from ._mean import mean


def mean_grade_average(grade_averages: Sequence[float]) -> float:
    return mean(grade_averages)
