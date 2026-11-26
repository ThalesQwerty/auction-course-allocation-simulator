"""Um `SimulationResult` virando as linhas do banco.

Vive aqui, e não no motor, para que `simulation/` continue sem saber o que é
persistência. O que entra é só o que o **mecanismo decidiu**: o que saiu da seed
volta do `prepare()` e não ocupa o banco.
"""
from __future__ import annotations

import json

from ..config import SimulationConfig
from ..simulation import SimulationResult

__all__ = [
    "classes_of",
    "period_of",
    "requests_of",
    "rounds_of",
    "student_periods_of",
    "student_rows",
]


def classes_of(simulation_id: int, outcome) -> list[tuple]:
    """A turma naquele período: o ambiente que a demanda de fundo produziu."""
    return [
        (
            simulation_id,
            outcome.report.period,
            snapshot.name,
            snapshot.seats,
            snapshot.requests,
            snapshot.filled,
            snapshot.granted,
            snapshot.exclusions,
            snapshot.approvals,
            snapshot.mean_price,
        )
        for snapshot in outcome.report.disciplines
    ]


def period_of(simulation_id: int, outcome, first_measured: int) -> tuple:
    """A linha de um período, no fechamento dele."""
    report = outcome.report
    overall = report.aggregate.overall
    return (
        simulation_id,
        report.period,
        int(report.period >= first_measured),
        None,
        None,
        None,
        len(report.rounds),
        overall.active,
        overall.metrics.students if overall.metrics else 0,
        report.graduated_now,
        report.dismissed_now,
    )


def rounds_of(simulation_id: int, outcome) -> list[tuple]:
    """As rodadas daquele período. `duracao_ms` é o relógio do **alocador**."""
    return [
        (
            simulation_id,
            outcome.report.period,
            report.round,
            None,
            None,
            round(report.allocation_seconds * 1000),
            report.overall.metrics.allocated if report.overall.metrics else 0,
        )
        for report in outcome.report.rounds
    ]


def student_periods_of(simulation_id: int, outcome) -> list[tuple]:
    """As linhas de aluno daquele período, juntando o ponto cru ao registro."""
    return [
        (
            simulation_id,
            point.student_id,
            point.period,
            point.grade_average,
            point.reserve,
            point.satisfaction,
            point.attendance,
            point.progress,
            point.mean_round,
            point.won,
            record.enrolled_hours,
            record.retained_hours,
            record.approved_hours,
            record.effective_load,
            record.credits_start,
            record.credits_spent,
            record.credits_returned,
        )
        for point in outcome.report.points
        for record in [_record_of(outcome, point)]
    ]


def requests_of(simulation_id: int, outcome) -> list[tuple]:
    """As solicitações **com atividade** daquele período, da coorte medida."""
    medidos = {point.student_id for point in outcome.report.points}
    return [
        (
            simulation_id,
            student_id,
            record.period,
            request.discipline,
            request.utility,
            json.dumps(request.bids) if any(request.bids) else None,
            None if request.won_round is None else max(1, request.won_round),
            request.paid,
            int(request.excluded),
            request.attempt,
            request.grade,
            int(request.approved),
            request.returned,
        )
        for student_id, record in outcome.records.items()
        if student_id in medidos
        for request in record.requests
        if _acted(request)
    ]


def _record_of(outcome, point):
    record = outcome.records.get(point.student_id)
    if record is None:
        raise ValueError(
            f"o aluno {point.student_id!r} tem ponto no período {point.period}"
            " e não tem registro: rode com o histórico da coorte medida"
        )
    return record


def student_rows(
    simulation_id: int, result: SimulationResult, config: SimulationConfig
) -> list[tuple]:
    """Todo aluno, com a flag da coorte medida: é com o fundo que se audita o
    estado estacionário."""
    return [
        (
            simulation_id,
            student.id,
            student.entry_period,
            int(
                not config.measured_cohorts or config.measures(student.entry_period)
            ),
            student.availability_anchor,
            student.selectivity_anchor,
            student.graduated_at,
            student.dismissed_at,
            student.grade_average,
            student.approved_hours,
            student.name,
        )
        for student in result.students
    ]


def _acted(request) -> bool:
    return (
        any(bid > 0 for bid in request.bids)
        or request.won_round is not None
        or request.grade is not None
    )
