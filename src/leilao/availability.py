"""A disponibilidade e a seletividade: os dois sorteios fora da nota."""
from __future__ import annotations

import numpy as np

from .config import SimulationConfig
from .equations import (
    lognormal_quantile,
    reflect,
    shock_scale,
    standard_normal_quantile,
)
from .population import Student

__all__ = ["draw_availability", "draw_selectivity"]


def draw_availability(
    students: list[Student],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, int], float]:
    """δ_{a,t} — as horas disponíveis de cada par (aluno, período)."""
    mean_log, sigma = config.availability_shape()
    anchors = np.array([student.availability_anchor for student in students])
    shocks = rng.normal(
        0.0,
        shock_scale(config.availability_stability),
        size=(len(students), config.periods),
    )
    return {
        (student.id, period + 1): lognormal_quantile(
            quantile=reflect(float(anchors[i] + shocks[i, period])),
            log_mean=mean_log,
            log_sd=sigma,
        )
        for i, student in enumerate(students)
        for period in range(config.periods)
    }


def draw_selectivity(
    students: list[Student], config: SimulationConfig
) -> dict[str, float]:
    """S_a — a seletividade, uma por aluno e constante no curso inteiro."""
    if config.selectivity_median <= 0.0:
        return {student.id: 0.0 for student in students}
    log_median = float(np.log(config.selectivity_median))
    return {
        student.id: float(
            np.exp(
                log_median
                + config.selectivity_sigma
                * standard_normal_quantile(student.selectivity_anchor)
            )
        )
        for student in students
    }
