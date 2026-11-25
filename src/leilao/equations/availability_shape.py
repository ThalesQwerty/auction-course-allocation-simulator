"""Os parâmetros da normal da disponibilidade, a partir do desvio e da chance."""
from __future__ import annotations

from ._normal import standard_normal_quantile


def availability_shape(
    *, hours_sd: float, full_load_rate: float, max_hours: float
) -> tuple[float, float]:
    """μ = W_a + σ · Φ⁻¹(P(W ≥ W_a)), pela mesma inversão da média da nota."""
    if hours_sd <= 0.0:
        raise ValueError("o desvio da disponibilidade deve ser > 0")
    if not 0.0 < full_load_rate < 1.0:
        raise ValueError("a chance de alcançar a carga máxima deve estar em (0, 1)")
    if max_hours <= 0.0:
        raise ValueError("a carga horária máxima deve ser > 0")
    return max_hours + hours_sd * standard_normal_quantile(full_load_rate), hours_sd
