"""A carga horária que o aluno vai de fato cursar no período."""
from __future__ import annotations

import math


def effective_load(*, availability: float) -> int:
    """O piso em horas inteiras: com W_a inteiro, alcançá-lo é exato."""
    if availability < 0.0:
        raise ValueError("a disponibilidade deve ser >= 0")
    return math.floor(availability)
