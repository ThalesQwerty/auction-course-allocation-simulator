"""Os alunos — o conjunto A (Seção 7.2) e o estado que anda com os períodos."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import SimulationConfig
from .equations import NEUTRAL, Behavior, grade_average
from .names import sample_names


@dataclass
class Student:
    """Um aluno a ∈ A e todo o seu histórico acadêmico."""

    id: str
    name: str
    credits: int
    entry_period: int = 1
    availability_anchor: float = 0.5
    selectivity_anchor: float = 0.5
    grades: dict[str, float] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)
    graduated_at: int | None = None
    dismissed_at: int | None = None

    @property
    def left_at(self) -> int | None:
        """O período em que o aluno deixou a simulação, por qualquer das duas"""
        return self.graduated_at if self.graduated_at is not None else self.dismissed_at
    behavior: Behavior = NEUTRAL

    @property
    def taken(self) -> set[str]:
        """H_a — disciplinas já cursadas, aprovadas ou não."""
        return set(self.attempts)

    def approved(self, min_grade: float) -> set[str]:
        """H^[apr]_a = { X ∈ H_a : n^[max]_{a,X} ≥ n_apr }."""
        return {name for name, grade in self.grades.items() if grade >= min_grade}

    def approved_hours(self, hours: dict[str, int], min_grade: float) -> int:
        """Σ_{x ∈ H̃_a} w_x — carga horária aprovada."""
        return sum(hours[name] for name in self.approved(min_grade))

    def grade_average(self, hours: dict[str, int]) -> float:
        """N_a — ver `equations.grade_average`."""
        return grade_average(taken=self.taken, grades=self.grades, hours=hours)


def generate_students(
    config: SimulationConfig, rng: np.random.Generator
) -> list[Student]:
    """Cria a população inteira a partir da seed. Todos começam em C_min"""
    names = sample_names(config.total_students(), rng)
    levels = rng.random(size=(config.total_students(), 2))
    students = []
    for index in range(config.total_students()):
        students.append(
            Student(
                id=f"a{index:05d}",
                name=names[index],
                credits=config.min_credits,
                entry_period=1 + index // config.students_per_period,
                availability_anchor=float(levels[index, 0]),
                selectivity_anchor=float(levels[index, 1]),
            )
        )
    return students
