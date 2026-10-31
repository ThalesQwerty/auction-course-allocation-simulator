"""O conjunto de métricas de um recorte (Seção 7.3.3).

Este módulo só **monta** o registro: cada número vem de uma função pura em
`equations/`, e é lá que a fórmula se revisa.
"""
from __future__ import annotations

from dataclasses import dataclass

from .equations import (
    RequestStates,
    demand_per_seat,
    exclusion_rate,
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
    "exclusion_rate",
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
    # --- as três grandezas da exclusão ------------------------------------
    #
    # Saem `None` em pleno período: a exclusão acontece depois da última
    # rodada, então só o recorte de fim de período tem o que contar. É a mesma
    # convenção do retorno de créditos.
    #
    # Note a divisão de trabalho com as de cima: as grandezas de **contagem**
    # (allocated, occupancy, utilization) ficam no alocado, porque a vaga saiu
    # do sistema tenha ou não sido cursada; as de **valor** (efficiency,
    # fairness, correlation) ficam no retido, porque o aluno não consumiu a
    # utilidade do que largou. A diferença entre as duas leituras é o
    # desperdício, e é o que estes três campos tornam visível.
    excluded: int | None  # vagas excluídas pelo recorte
    exclusion_rate: float | None  # ε — `exclusion_rate`
    effective_utilization: float | None  # carga retida ÷ W_a, média
    # Os seis estados de solicitação, em **média por aluno** — a seção
    # "Solicitações de disciplinas". Ver `equations.request_states`.
    request_states: RequestStates | None
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
    excluded: int | None = None,
    effective_utilizations: list[float] | None = None,
    states: list[RequestStates] | None = None,
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
        excluded=excluded,
        exclusion_rate=(
            exclusion_rate(excluded=excluded, allocated=allocated)
            if excluded is not None
            else None
        ),
        effective_utilization=(
            mean(effective_utilizations) if effective_utilizations is not None else None
        ),
        request_states=RequestStates.average(states) if states is not None else None,
        scarcity=mean(scarcities),
        contention=mean(contentions),
        mean_grade_average=mean_grade_average(grade_averages),
        correlation=pearson(grade_averages, satisfactions),
        semestralization=mean(semestralizations),
    )
