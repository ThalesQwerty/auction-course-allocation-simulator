"""Simulação multi-período da matrícula universitária (Seção 7.2)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from ..config import SimulationConfig
from ..population import Student
from ..steps import OnStep, PeriodSteps
from ..equations import (
    grade_histogram,
    interest_histogram,
    progress,
)
from ..equations._mean import mean
from .period import PeriodOutcome, run_period
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
    StudentPeriodPoint,
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
    "StudentPeriodPoint",
    "StudentPeriodRecord",
    "StudentSummary",
    "run_simulation",
]


def _approved_hours(
    student, config: SimulationConfig, draws, *, elective: bool
) -> int:
    """As horas aprovadas de um lado só da exigência."""
    optativas = {d.name for d in config.disciplines if d.elective}
    return sum(
        draws.discipline_hours[name]
        for name in student.approved(config.min_grade)
        if (name in optativas) == elective
    )


Histories = Literal["nenhum", "medidos", "todos"]
"""De quem se guarda o roteiro período a período. O roteiro da coorte medida é
30 MB por simulação no cenário cheio, e o de todo mundo é 902 MB."""


def recorded_students(
    config: SimulationConfig, students: list[Student], histories: "Histories"
) -> set[str]:
    if histories == "nenhum":
        return set()
    if histories == "medidos" and config.measured_cohorts:
        return {s.id for s in students if config.measures(s.entry_period)}
    return {s.id for s in students}


def run_simulation(
    config: SimulationConfig,
    *,
    histories: "Histories" = "todos",
    on_period: Callable[[PeriodOutcome], None] | None = None,
    on_step: OnStep | None = None,
) -> SimulationResult:
    """Roda a simulação inteira. Determinística: mesma config, mesmo resultado.

    Com `on_period`, cada período é entregue no fechamento e **não fica**: nem o
    relatório nem os registros dele são acumulados, de modo que a memória do
    processo não cresce com o horizonte. O resultado sai então sem `periods` e
    sem `histories`, e quem os tem é quem recebeu os períodos.
    """
    draws = prepare(config)
    students = draws.students
    recorded = recorded_students(config, students, histories)

    periods: list[PeriodReport] = []
    history: dict[str, list[StudentPeriodRecord]] = {s.id: [] for s in students}
    satisfactions: dict[str, list[float]] = {s.id: [] for s in students}
    reserves: dict[str, list[float]] = {s.id: [] for s in students}
    attendances: dict[str, list[float]] = {s.id: [] for s in students}
    won_rounds: dict[str, list[int]] = {s.id: [] for s in students}
    enrollments: dict[str, int] = {s.id: 0 for s in students}
    first_grades: list[float] = []

    for period in range(1, config.periods + 1):
        active = [
            s for s in students if s.entry_period <= period and s.left_at is None
        ]
        if not active:
            break

        steps = PeriodSteps(on_step, period=period)
        steps.started()
        outcome = run_period(
            config=config,
            draws=draws,
            period=period,
            active=active,
            enrollments=enrollments,
            recorded=recorded,
            steps=steps,
        )
        if outcome is None:
            break
        steps.closed()

        if on_period is None:
            periods.append(outcome.report)
        else:
            on_period(outcome)
        first_grades.extend(outcome.first_grades)
        for student_id, value in outcome.satisfaction.items():
            satisfactions[student_id].append(value)
        if period >= config.first_measured_period:
            for student_id, value in outcome.reserve.items():
                reserves[student_id].append(value)
            for student_id, taken in outcome.attendance.items():
                if taken is not None:
                    attendances[student_id].append(taken)
            for student_id, rounds in outcome.won_rounds.items():
                won_rounds[student_id].extend(rounds)
        if on_period is None:
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
                mean_reserve=mean(reserves[s.id]),
                mean_attendance=(
                    mean(attendances[s.id]) if attendances[s.id] else None
                ),
                mean_round=(
                    mean([float(r) for r in won_rounds[s.id]])
                    if won_rounds[s.id]
                    else None
                ),
                progress=progress(
                    approved_required_hours=_approved_hours(
                        s, config, draws, elective=False
                    ),
                    approved_elective_hours=_approved_hours(
                        s, config, draws, elective=True
                    ),
                    required_hours=sum(
                        draws.discipline_hours[name]
                        for name in config.required_disciplines()
                    ),
                    elective_hours_needed=config.elective_hours,
                ),
                measured_periods=len(reserves[s.id]),
                graduated_at=s.graduated_at,
                dismissed_at=s.dismissed_at,
            )
            for s in students
        ],
        histories=(
            []
            if on_period is not None
            else [
                StudentHistory(student_id=s.id, periods=history[s.id])
                for s in students
                if s.id in recorded
            ]
        ),
        disciplines=list(draws.seats),
        classes=dict(draws.discipline_of),
        curriculum_periods=draws.curriculum,
        interest_distribution=interest_histogram(draws.interest_rows.values()),
        grade_distribution=grade_histogram(first_grades),
        measured_cohort=config.measured_cohort,
        measured_cohorts=config.measured_cohorts,
        warmup_periods=config.warmup_periods,
    )
