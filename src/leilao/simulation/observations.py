"""A linha crua de cada aluno medido num período."""
from __future__ import annotations

from ..config import SimulationConfig
from ..equations._mean import mean
from ..population import Student
from .reports import StudentPeriodPoint
from .snapshots import Measurements, measured_students

__all__ = ["period_points"]


def period_points(
    *,
    config: SimulationConfig,
    active: list[Student],
    period: int,
    values: Measurements,
    won_rounds: dict[str, list[int]],
) -> list[StudentPeriodPoint]:
    """As linhas do período: uma por aluno da coorte medida, no fechamento."""
    if period < config.first_measured_period:
        return []
    return [
        StudentPeriodPoint(
            student_id=student.id,
            period=period,
            grade_average=values.grade_averages[student.id],
            reserve=values.reserves[student.id],
            satisfaction=values.satisfactions[student.id],
            attendance=(
                values.attendances[student.id]
                if values.attendances is not None
                else None
            ),
            progress=values.progresses[student.id],
            mean_round=(
                mean([float(r) for r in won_rounds[student.id]])
                if won_rounds.get(student.id)
                else None
            ),
            won=len(values.won[student.id]),
        )
        for student in measured_students(
            config=config, students=active, period=period
        )
    ]
