"""O conjunto de métricas de um recorte (Seção 7.3.3).

Este módulo só **monta** o registro: cada número vem de uma função pura em
`equations/`, e é lá que a fórmula se revisa.
"""
from __future__ import annotations

from dataclasses import dataclass

from .equations import (
    demand_per_seat,
    jain_index,
    mean_grade_average,
    mean_satisfaction,
    occupancy,
    pearson,
    semestralization,
)
from .equations._mean import mean

__all__ = [
    "Metrics",
    "compute_metrics",
    "demand_per_seat",
    "jain_index",
    "pearson",
    "semestralization",
]


@dataclass(frozen=True)
class Metrics:
    """As métricas de um recorte num instante — uma rodada ou um período.

    Cada campo aponta para a função de `equations/` que o calcula; o que está
    aqui é a lista do que se publica, não como se calcula.
    """

    students: int  # |A^(t)| medidos — sem os calouros do período
    allocated: int  # vagas obtidas pelo recorte
    allocations_per_student: float
    efficiency: float  # ψ̄ — `mean_satisfaction`
    utilization: float  # aproveitamento de carga — `utilization`
    fidelity: float  # cosseno da mensagem — `message_fidelity`
    fairness: float  # φ — `jain_index`
    occupancy: float  # θ — `occupancy`
    scarcity: float  # demanda potencial — `demand_per_seat`
    contention: float  # demanda efetiva — `demand_per_seat`
    mean_grade_average: float  # N̄ — `mean_grade_average`
    correlation: float  # λ — `pearson`
    semestralization: float  # σ̄ — `semestralization`


def compute_metrics(
    *,
    satisfactions: list[float],
    utilizations: list[float],
    fidelities: list[float],
    grade_averages: list[float],
    semestralizations: list[float],
    scarcities: list[float],
    contentions: list[float],
    allocated: int,
    total_seats: int,
) -> Metrics:
    """Agrega as métricas de um recorte de alunos.

    `total_seats` é sempre a oferta de **toda a universidade**, mesmo num
    recorte: a ocupação vira a fração das vagas que foi para aquele grupo, e a
    soma dos grupos reproduz a eq. (54). Escassez e concorrência não seguem
    essa convenção — são médias dos alunos, pelo motivo em `demand_per_seat`.
    """
    return Metrics(
        students=len(satisfactions),
        allocated=allocated,
        allocations_per_student=allocated / len(satisfactions) if satisfactions else 0.0,
        efficiency=mean_satisfaction(satisfactions),
        utilization=mean(utilizations),
        fidelity=mean(fidelities),
        fairness=jain_index(satisfactions),
        occupancy=occupancy(allocated=allocated, total_seats=total_seats),
        scarcity=mean(scarcities),
        contention=mean(contentions),
        mean_grade_average=mean_grade_average(grade_averages),
        correlation=pearson(grade_averages, satisfactions),
        semestralization=mean(semestralizations),
    )
