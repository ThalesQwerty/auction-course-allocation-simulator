"""Simulação multi-período da matrícula universitária (Seção 7.2)."""
from __future__ import annotations

from ..config import SimulationConfig
from ..equations import (
    grade_histogram,
    interest_histogram,
)
from ..equations._mean import mean
from .period import run_period
from .reports import (
    GUARANTEED_ROUND,
    DisciplineSnapshot,
    GroupSnapshot,
    PeriodReport,
    PriceStats,
    RequestRecord,
    RoundReport,
    SimulationResult,
    StudentHistory,
    StudentPeriodRecord,
    StudentSummary,
)
from .setup import prepare
from .snapshots import CELL_SEP

__all__ = [
    "CELL_SEP",
    "GUARANTEED_ROUND",
    "DisciplineSnapshot",
    "GroupSnapshot",
    "PeriodReport",
    "PriceStats",
    "RequestRecord",
    "RoundReport",
    "SimulationResult",
    "StudentHistory",
    "StudentPeriodRecord",
    "StudentSummary",
    "run_simulation",
]


def run_simulation(
    config: SimulationConfig, *, keep_histories: bool = True
) -> SimulationResult:
    """Roda a simulação inteira. Determinística: mesma config, mesmo resultado."""
    draws = prepare(config)
    students = draws.students

    periods: list[PeriodReport] = []
    history: dict[str, list[StudentPeriodRecord]] = {s.id: [] for s in students}
    satisfactions: dict[str, list[float]] = {s.id: [] for s in students}
    enrollments: dict[str, int] = {s.id: 0 for s in students}
    first_grades: list[float] = []

    for period in range(1, config.periods + 1):
        active = [
            s for s in students if s.entry_period <= period and s.left_at is None
        ]
        if not active:
            break

        outcome = run_period(
            config=config,
            draws=draws,
            period=period,
            active=active,
            enrollments=enrollments,
            keep_records=keep_histories,
        )
        if outcome is None:
            break

        periods.append(outcome.report)
        first_grades.extend(outcome.first_grades)
        for student_id, value in outcome.satisfaction.items():
            satisfactions[student_id].append(value)
        for student_id, record in outcome.records.items():
            history[student_id].append(record)

    return SimulationResult(
        periods=periods,
        students=[
            StudentSummary(
                id=s.id,
                name=s.name,
                entry_period=s.entry_period,
                availability_anchor=s.availability_anchor,
                selectivity_anchor=s.selectivity_anchor,
                grade_average=s.grade_average(draws.discipline_hours),
                approved_hours=s.approved_hours(
                    draws.discipline_hours, config.min_grade
                ),
                hours_to_graduate=draws.hours_to_graduate,
                credits=s.credits,
                enrollments=enrollments[s.id],
                approvals=len(s.approved(config.min_grade)),
                mean_satisfaction=mean(satisfactions[s.id]),
                graduated_at=s.graduated_at,
                dismissed_at=s.dismissed_at,
            )
            for s in students
        ],
        histories=(
            [StudentHistory(student_id=s.id, periods=history[s.id]) for s in students]
            if keep_histories
            else []
        ),
        disciplines=list(draws.seats),
        classes=dict(draws.discipline_of),
        curriculum_periods=draws.curriculum,
        interest_distribution=interest_histogram(draws.interest_rows.values()),
        grade_distribution=grade_histogram(first_grades),
        warmup_periods=config.warmup_periods,
    )
