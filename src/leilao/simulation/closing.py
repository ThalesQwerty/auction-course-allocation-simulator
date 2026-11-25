"""O fim do período: exclusão, notas, retorno de créditos, conclusão e"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import SimulationConfig
from ..equations import (
    credit_return,
    effective_load,
    grade_for_attempt,
    has_graduated,
    next_budget,
    period_return,
    retained_set,
)
from ..population import Student
from .setup import Draws
from .state import PeriodState


@dataclass
class PeriodClosing:
    """O que o fim do período produziu, para os relatórios."""

    approvals: dict[str, int]
    attempts: dict[tuple[str, str], tuple[int, float]] = field(default_factory=dict)
    returned: dict[tuple[str, str], int] = field(default_factory=dict)
    credits_returned: dict[str, int] = field(default_factory=dict)
    retained: dict[str, set[str]] = field(default_factory=dict)
    excluded: dict[str, list[str]] = field(default_factory=dict)
    exclusions: dict[str, int] = field(default_factory=dict)
    load: dict[str, int] = field(default_factory=dict)
    first_grades: list[float] = field(default_factory=list)
    graduated_now: int = 0
    dismissed_now: int = 0


def _grade(
    *,
    student: Student,
    name: str,
    discipline: str,
    attempt: int,
    draws: Draws,
    config: SimulationConfig,
) -> float:
    """A nota desta tentativa — ver `equations.grade_for_attempt`."""
    mean = draws.grade_means.of(config, attempt - 1)
    return grade_for_attempt(
        quantile=draws.grade_quantiles[
            (student.id, discipline, min(attempt - 1, config.attempt_cap() - 1))
        ],
        grade_mean=mean,
        grade_sd=config.grade_sd,
    )


def close_period(
    *,
    config: SimulationConfig,
    draws: Draws,
    active: list[Student],
    state: PeriodState,
    period: int,
    utilities: dict[str, dict[str, float]],
    enrollments: dict[str, int],
) -> PeriodClosing:
    closing = PeriodClosing(
        approvals={name: 0 for name in draws.seats},
        exclusions={name: 0 for name in draws.seats},
    )

    for student in active:
        allocated = state.won[student.id]
        load = effective_load(
            availability=draws.availability[(student.id, period)]
        )
        kept = retained_set(
            utilities=utilities[student.id],
            hours=draws.hours,
            obtained=allocated,
            load=load,
        )
        closing.load[student.id] = load
        retained = set(kept)
        excluded = sorted(allocated - retained)
        closing.retained[student.id] = retained
        closing.excluded[student.id] = excluded

        enrollments[student.id] += len(retained)
        gammas: list[int] = []

        for name in excluded:
            closing.exclusions[name] += 1
            closing.returned[(student.id, name)] = 0
            gammas.append(0)

        for name in kept:
            discipline = draws.discipline_of[name]
            attempt = student.attempts.get(discipline, 0) + 1
            student.attempts[discipline] = attempt
            grade = _grade(
                student=student,
                name=name,
                discipline=discipline,
                attempt=attempt,
                draws=draws,
                config=config,
            )
            if attempt == 1:
                closing.first_grades.append(grade)
            student.grades[discipline] = max(
                student.grades.get(discipline, 0.0), grade
            )
            closing.attempts[(student.id, discipline)] = (attempt, grade)
            if student.grades[discipline] >= config.min_grade:
                closing.approvals[name] += 1

            gamma = (
                credit_return(
                    paid=state.paid.get((student.id, name), 0),
                    grade=student.grades[discipline],
                )
                if config.uses_credits
                else 0
            )
            closing.returned[(student.id, name)] = gamma
            gammas.append(gamma)

        closing.credits_returned[student.id] = sum(gammas)

        if config.uses_credits:
            student.credits = next_budget(
                started_with=student.credits,
                spent=state.spent[student.id],
                period_return=period_return(returns=gammas),
                min_credits=config.min_credits,
                max_credits=config.max_credits,
            )

        if has_graduated(
            approved=student.approved(config.min_grade),
            required=draws.required,
            elective_hours_by_discipline=draws.elective_hours_by_discipline,
            elective_hours_needed=config.elective_hours,
        ):
            student.graduated_at = period
            closing.graduated_now += 1
        elif config.dismissal_period(student.entry_period) == period:
            student.dismissed_at = period
            closing.dismissed_now += 1

    return closing
