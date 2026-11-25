"""O conjunto de métricas de um recorte (Seção 7.3.3)."""
from __future__ import annotations

from dataclasses import dataclass

from .equations import (
    RequestStates,
    demand_per_seat,
    exclusion_rate,
    jain_index,
    mean_grade_average,
    mean_satisfaction,
    progress,
    semestralization,
)
from .equations._mean import mean

__all__ = [
    "Metrics",
    "compute_metrics",
    "demand_per_seat",
    "exclusion_rate",
    "jain_index",
    "progress",
    "semestralization",
]


@dataclass(frozen=True)
class Metrics:
    """As métricas de um recorte num instante — uma rodada ou um período."""

    students: int
    allocated: int
    allocations_per_student: float
    satisfaction: float
    fairness: float
    progress: float
    attendance: float | None
    attendance_students: int | None
    excluded: int | None
    exclusion_rate: float | None
    request_states: RequestStates | None
    fidelity: float
    scarcity: float
    contention: float
    mean_grade_average: float
    semestralization: float


def compute_metrics(
    *,
    satisfactions: list[float],
    progresses: list[float],
    fidelities: list[float],
    grade_averages: list[float],
    semestralizations: list[float],
    scarcities: list[float],
    contentions: list[float],
    allocated: int,
    total_seats: int,
    attendances: list[float] | None = None,
    excluded: int | None = None,
    states: list[RequestStates] | None = None,
) -> Metrics:
    """Agrega as métricas de um recorte de alunos."""
    kept = [value for value in (attendances or []) if value is not None]
    return Metrics(
        students=len(satisfactions),
        allocated=allocated,
        allocations_per_student=allocated / len(satisfactions) if satisfactions else 0.0,
        satisfaction=mean_satisfaction(satisfactions),
        fairness=jain_index(satisfactions),
        progress=mean(progresses),
        attendance=(mean(kept) if attendances is not None and kept else None),
        attendance_students=(len(kept) if attendances is not None else None),
        excluded=excluded,
        exclusion_rate=(
            exclusion_rate(excluded=excluded, allocated=allocated)
            if excluded is not None
            else None
        ),
        request_states=RequestStates.average(states) if states is not None else None,
        fidelity=mean(fidelities),
        scarcity=mean(scarcities),
        contention=mean(contentions),
        mean_grade_average=mean_grade_average(grade_averages),
        semestralization=mean(semestralizations),
    )
