"""A disponibilidade e a seletividade: os dois sorteios fora da nota."""
from __future__ import annotations

import numpy as np

from .config import SimulationConfig
from .equations import (
    availability_hours,
    reflect,
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
    mean, sd = config.availability_shape()
    anchors = np.array([student.availability_anchor for student in students])
    shocks = rng.normal(
        0.0,
        config.availability_fluctuation,
        size=(len(students), config.periods),
    )
    return {
        (student.id, period + 1): availability_hours(
            quantile=reflect(float(anchors[i] + shocks[i, period])),
            hours_mean=mean,
            hours_sd=sd,
            max_hours=config.max_hours,
        )
        for i, student in enumerate(students)
        for period in range(config.periods)
    }


def draw_selectivity(
    students: list[Student],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, int], float]:
    """S_{a,t} — a seletividade de cada par (aluno, período)."""
    anchors = np.array([student.selectivity_anchor for student in students])
    shocks = rng.normal(
        0.0,
        config.selectivity_fluctuation,
        size=(len(students), config.periods),
    )
    return {
        (student.id, period + 1): float(
            np.exp(
                config.selectivity_mean
                + config.selectivity_sigma
                * standard_normal_quantile(
                    reflect(float(anchors[i] + shocks[i, period]))
                )
            )
        )
        for i, student in enumerate(students)
        for period in range(config.periods)
    }
