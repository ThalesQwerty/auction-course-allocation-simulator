"""A inicialização: tudo o que vem da seed, antes do primeiro período."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..availability import draw_availability, draw_selectivity
from ..behavior import InterestMatrix, draw_interest, draw_schedule_interest
from ..config import SimulationConfig
from ..grading import GradeMeans, draw_grade_quantiles
from ..equations import per_agent, stochastic_perturbations
from ..population import Student, generate_students


@dataclass(frozen=True)
class Draws:
    """O que a seed produziu, mais o que se deriva do cenário uma vez só."""

    students: list[Student]
    grade_quantiles: dict[tuple[str, str, int], float]
    selectivity: dict[tuple[str, int], float]
    grade_means: GradeMeans
    availability: dict[tuple[str, int], float]
    schedule_rows: InterestMatrix
    interest_rows: InterestMatrix
    epsilon: dict[tuple[str, str], float]
    student_epsilon: dict[str, float]

    hours: dict[str, int]
    seats: dict[str, int]
    discipline_hours: dict[str, int]
    classes: dict[str, tuple[str, ...]]
    discipline_of: dict[str, str]
    schedule_of: dict[str, str]
    conflicts: dict[str, tuple[str, ...]]
    exclusions: tuple[frozenset[str], ...]
    curriculum: dict[str, int]
    entry_courses: list[str]
    entry_offsets: dict[str, int]
    required: set[str]
    elective_hours_by_discipline: dict[str, int]
    hours_to_graduate: int
    total_seats: int
    entry_periods: list[int]


def prepare(config: SimulationConfig) -> Draws:
    rng = np.random.default_rng(config.seed)
    students = generate_students(config, rng)
    grade_quantiles = draw_grade_quantiles(
        students, config.disciplines, config, rng
    )
    availability = draw_availability(students, config, rng)
    selectivity = draw_selectivity(students, config, rng)
    interest_rows = draw_interest(students, config, rng)
    schedule_rows = draw_schedule_interest(students, config, rng)

    epsilon = stochastic_perturbations(
        [(s.id, d.name) for s in students for d in config.disciplines],
        num_agents=max(len(students), 1),
        num_goods=max(len(config.disciplines), 1),
        seed=config.seed,
    )

    return Draws(
        students=students,
        grade_quantiles=grade_quantiles,
        selectivity=selectivity,
        grade_means=GradeMeans(),
        availability=availability,
        interest_rows=interest_rows,
        schedule_rows=schedule_rows,
        epsilon=epsilon,
        student_epsilon=per_agent(epsilon),
        hours=config.hours_by_class(),
        seats=config.seats_by_class(),
        discipline_hours=config.hours_by_discipline(),
        classes=config.classes_by_discipline(),
        discipline_of=config.discipline_by_class(),
        schedule_of=config.schedule_by_class(),
        conflicts=config.conflict_groups(),
        exclusions=config.exclusion_cliques(),
        curriculum=config.curriculum_periods(),
        entry_courses=config.entry_disciplines(),
        entry_offsets=config.entry_offsets() or {},
        required=config.required_disciplines(),
        elective_hours_by_discipline=config.elective_hours_by_discipline(),
        hours_to_graduate=config.hours_to_graduate(),
        total_seats=sum(d.seats for d in config.disciplines),
        entry_periods=sorted({s.entry_period for s in students}),
    )
