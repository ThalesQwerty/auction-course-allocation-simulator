"""As horas que um quantil da disponibilidade vale."""
from __future__ import annotations

from ._normal import standard_normal_quantile


def availability_hours(
    *, quantile: float, hours_mean: float, hours_sd: float, max_hours: float
) -> float:
    """W^[pos] = clamp_[0, W_a](μ + σ · Φ⁻¹(q))."""
    if hours_sd <= 0.0:
        raise ValueError("o desvio da disponibilidade deve ser > 0")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("o quantil deve estar em [0, 1]")
    latente = hours_mean + hours_sd * standard_normal_quantile(quantile)
    return min(max_hours, max(0.0, latente))
