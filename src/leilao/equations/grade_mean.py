"""A média da normal das notas, dada a taxa de aprovação."""
from __future__ import annotations

from ._normal import standard_normal_quantile


def grade_mean(*, min_grade: float, grade_sd: float, approval_rate: float) -> float:
    """μ, a média da normal cuja chance de alcançar `min_grade` é a declarada."""
    if grade_sd <= 0.0:
        raise ValueError("o desvio padrão das notas deve ser > 0")
    if not 0.0 < approval_rate < 1.0:
        raise ValueError("a probabilidade de aprovação deve estar em (0, 1)")
    return min_grade + grade_sd * standard_normal_quantile(approval_rate)
