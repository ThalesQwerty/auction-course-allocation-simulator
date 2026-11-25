"""A nota: o quantil de cada tentativa (Seção 7.2.2)."""
from __future__ import annotations

import numpy as np

from .config import Discipline, SimulationConfig
from .equations import (
    attempt_approval,
    credit_return,
    grade_for_attempt,
    grade_mean,
)
from .equations.grade_histogram import BINS as DISTRIBUTION_BINS
from .equations.grade_histogram import grade_histogram as grade_distribution
from .population import Student

__all__ = [
    "DISTRIBUTION_BINS",
    "GradeMeans",
    "credit_return",
    "draw_grade_quantiles",
    "grade_distribution",
    "grade_for_attempt",
]


def draw_grade_quantiles(
    students: list[Student],
    disciplines: list[Discipline],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> dict[tuple[str, str, int], float]:
    """q_{a,X,k} — o quantil de cada (aluno, disciplina, tentativa)."""
    attempts = max(1, config.attempt_cap())
    draws = rng.random(size=(len(students), len(disciplines), attempts))
    return {
        (student.id, discipline.name, attempt): float(draws[i, j, attempt])
        for i, student in enumerate(students)
        for j, discipline in enumerate(disciplines)
        for attempt in range(attempts)
    }


class GradeMeans:
    """A média da normal por número de repetições."""

    def __init__(self) -> None:
        self._means: dict[int, float] = {}

    def of(self, config: SimulationConfig, previous_attempts: int) -> float:
        key = previous_attempts
        if key not in self._means:
            rate = attempt_approval(
                approval_rate=config.approval_rate,
                repetition_gain=config.repetition_gain,
                previous_attempts=previous_attempts,
            )
            self._means[key] = grade_mean(
                min_grade=config.min_grade,
                grade_sd=config.grade_sd,
                approval_rate=rate,
            )
        return self._means[key]
