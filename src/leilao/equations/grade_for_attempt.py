"""A nota de uma tentativa, a partir do quantil sorteado."""
from __future__ import annotations

import math

from ._normal import standard_normal_quantile

MIN_GRADE = 0.0
MAX_GRADE = 10.0


def grade_for_attempt(
    *, quantile: float, grade_mean: float, grade_sd: float
) -> float:
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("o quantil deve estar em [0, 1]")
    if grade_sd <= 0.0:
        raise ValueError("o desvio padrão das notas deve ser > 0")
    latent = grade_mean + grade_sd * standard_normal_quantile(quantile)
    return min(MAX_GRADE, max(MIN_GRADE, math.floor(10.0 * latent) / 10.0))
