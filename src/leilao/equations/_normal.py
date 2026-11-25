"""A normal padrão: Φ e a inversa dela."""
from __future__ import annotations

import math
from statistics import NormalDist

_STANDARD = NormalDist()

QUANTILE_GUARD = 1e-15


def standard_normal_cdf(value: float) -> float:
    """Φ(z)."""
    return 0.5 * math.erfc(-value / math.sqrt(2.0))


def standard_normal_quantile(probability: float) -> float:
    """Φ⁻¹(p), com as bordas afastadas do infinito."""
    if not 0.0 <= probability <= 1.0:
        raise ValueError("a probabilidade deve estar em [0, 1]")
    inner = min(1.0 - QUANTILE_GUARD, max(QUANTILE_GUARD, probability))
    return _STANDARD.inv_cdf(inner)


_A = (
    -3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
    1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00,
)
_B = (
    -5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
    6.680131188771972e+01, -1.328068155288572e+01,
)
_C = (
    -7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
    -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00,
)
_D = (
    7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
    3.754408661907416e+00,
)
_TAIL = 0.02425


def standard_normal_quantiles(probabilities):
    """Φ⁻¹ sobre um array inteiro, pela aproximação de Acklam."""
    import numpy as np

    p = np.clip(np.asarray(probabilities, dtype=float), QUANTILE_GUARD,
                1.0 - QUANTILE_GUARD)
    out = np.empty_like(p)

    def tail(value):
        q = np.sqrt(-2.0 * np.log(value))
        return (
            ((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q
            + _C[5]
        ) / ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)

    low = p < _TAIL
    high = p > 1.0 - _TAIL
    mid = ~(low | high)

    out[low] = tail(p[low])
    out[high] = -tail(1.0 - p[high])
    q = p[mid] - 0.5
    r = q * q
    out[mid] = (
        (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5])
        * q
        / (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0)
    )
    return out
