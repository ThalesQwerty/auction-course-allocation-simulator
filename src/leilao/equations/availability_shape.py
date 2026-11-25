"""Os parâmetros da log-normal da disponibilidade, a partir de moda e chance."""
from __future__ import annotations

import math
from statistics import NormalDist

_STANDARD = NormalDist()


def availability_shape(
    *, mode_hours: float, full_load_rate: float, max_hours: float
) -> tuple[float, float]:
    if mode_hours <= 0.0:
        raise ValueError("a moda da disponibilidade deve ser > 0")
    if not 0.0 < full_load_rate < 1.0:
        raise ValueError("a chance de alcançar a carga máxima deve estar em (0, 1)")
    if max_hours <= 0.0:
        raise ValueError("a carga horária máxima deve ser > 0")
    threshold = max_hours - 0.5
    if mode_hours >= threshold:
        raise ValueError(
            "a moda da disponibilidade deve ficar abaixo da carga horária máxima"
        )
    span = math.log(threshold / mode_hours)
    z = _STANDARD.inv_cdf(1.0 - full_load_rate)
    sigma = 0.5 * (-z + math.sqrt(z * z + 4.0 * span))
    return math.log(mode_hours) + sigma * sigma, sigma
