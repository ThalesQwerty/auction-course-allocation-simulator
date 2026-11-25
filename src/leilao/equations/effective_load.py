"""A carga horária que o aluno vai de fato cursar no período."""
from __future__ import annotations


def effective_load(*, availability: float) -> int:
    if availability < 0.0:
        raise ValueError("a disponibilidade deve ser >= 0")
    return round(availability)
