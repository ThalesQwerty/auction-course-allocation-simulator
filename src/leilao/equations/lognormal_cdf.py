"""A acumulada da log-normal."""
from __future__ import annotations

import math

from ._normal import standard_normal_cdf, standard_normal_quantile


def lognormal_cdf(*, value: float, log_mean: float, log_sd: float) -> float:
    if log_sd <= 0.0:
        raise ValueError("o desvio logarítmico deve ser > 0")
    if value <= 0.0:
        return 0.0
    return standard_normal_cdf((math.log(value) - log_mean) / log_sd)


def lognormal_quantile(*, quantile: float, log_mean: float, log_sd: float) -> float:
    """F⁻¹(q) = exp(μ + σ · Φ⁻¹(q)) — a carga que aquele quantil vale."""
    if log_sd <= 0.0:
        raise ValueError("o desvio logarítmico deve ser > 0")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("o quantil deve estar em [0, 1]")
    return math.exp(log_mean + log_sd * standard_normal_quantile(quantile))
