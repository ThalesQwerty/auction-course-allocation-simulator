"""Schemas Pydantic para a API — o corpo da requisição já É o cenário completo
(sem persistência): a interface monta tudo no navegador e manda de uma vez.

São duas entradas: `/run` recebe um leilão isolado (agentes, bens e lances
explícitos) e `/simulate` recebe a configuração de uma simulação multi-período
completa, em que alunos, utilidades e notas são gerados a partir da seed.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..auction import AuctionResult
from ..config import CreditReturnPolicy


class AgentIn(BaseModel):
    id: str
    capacity: float = Field(gt=0, description="W_a — carga horária máxima do aluno")
    budget: int = Field(ge=0, description="C_a — orçamento inicial de créditos")


class GoodIn(BaseModel):
    id: str
    quantity: int = Field(ge=0, description="q_x — vagas na disciplina")
    weight: float = Field(gt=0, description="w_x — carga horária da disciplina")


class BidIn(BaseModel):
    agent_id: str
    good_id: str
    credits: int = Field(gt=0, description="c_{a,x} — créditos apostados no lance")


class RunRequest(BaseModel):
    agents: list[AgentIn] = Field(default_factory=list)
    goods: list[GoodIn] = Field(default_factory=list)
    bids: list[BidIn] = Field(default_factory=list)
    exclusions: list[list[str]] = Field(
        default_factory=list, description="cliques de bens mutuamente excludentes (choque de horário)"
    )
    seed: int = 0


class RunResponse(BaseModel):
    """Chaves de pares (agente, bem) são serializadas como "agent_id|good_id"."""

    allocation: dict[str, int]
    prices: dict[str, int]
    consumption: dict[str, int]
    remaining_budget: dict[str, int]
    remaining_capacity: dict[str, float]

    @staticmethod
    def from_result(result: AuctionResult) -> "RunResponse":
        return RunResponse(
            allocation={f"{a}|{g}": v for (a, g), v in result.allocation.items()},
            prices=result.prices,
            consumption={f"{a}|{g}": v for (a, g), v in result.consumption.items()},
            remaining_budget=result.remaining_budget,
            remaining_capacity=result.remaining_capacity,
        )


class DisciplineIn(BaseModel):
    name: str
    seats: int = Field(ge=0, description="q_x — vagas")
    hours: int = Field(gt=0, description="w_x — carga horária")


class CourseIn(BaseModel):
    name: str
    students_per_generation: int = Field(
        ge=0,
        description="alunos que ingressam a cada período com ingresso; a população é isto × L",
    )
    hours_to_graduate: int = Field(ge=0, description="S_k — eq. (39)")
    required: list[str] = Field(default_factory=list, description="M_k — obrigatórias")
    electives: list[str] = Field(default_factory=list, description="O_k — optativas")


class SimulateRequest(BaseModel):
    """Configuração completa de um cenário (Seção 7.2)."""

    disciplines: list[DisciplineIn] = Field(default_factory=list)
    courses: list[CourseIn] = Field(default_factory=list)
    periods: int = Field(default=1, ge=1, le=40, description="|T| — períodos letivos")
    entry_periods: int | None = Field(
        default=None,
        ge=1,
        le=40,
        description=(
            "L — em quantos dos |T| períodos entra geração nova, contados do primeiro. "
            "Null = em todos. Com L < |T| há uma fase de drenagem depois do último "
            "ingresso, em que a população só diminui."
        ),
    )
    max_residence: int = Field(
        default=0,
        ge=0,
        le=40,
        description=(
            "T_max — períodos que o aluno pode permanecer antes de ser jubilado. "
            "0 = sem jubilamento."
        ),
    )
    rounds: int = Field(default=1, ge=1, le=10, description="|R| — rodadas por período")
    min_grade: float = Field(default=5.0, gt=0, le=10, description="n_min")
    base_credits: int = Field(default=10, ge=1, description="Gamma_min — créditos base")
    max_hours: int = Field(default=360, ge=1, description="W_a — carga horária máxima")
    learning_gain: float = Field(
        default=2.5, gt=0, le=10, description="ganho de nota por recursada — eq. (33)"
    )
    # f_gamma — eq. (34); as políticas estão em `grading.credit_return`.
    credit_return: CreditReturnPolicy = "none"
    seed: int = 0
    include_histories: bool = Field(
        default=False,
        description=(
            "detalhe período a período de cada aluno. Fica de fora por padrão porque "
            "é ~50x o resto da resposta num cenário grande (40 MB com 1500 alunos) e "
            "só alimenta a tela individual; a seed garante que reexecutar reconstrói "
            "exatamente o mesmo detalhe."
        ),
    )


class MetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    students: int
    allocated: int
    allocations_per_student: float
    efficiency: float  # eq. (53)
    fairness: float  # eq. (55)
    occupancy: float  # eq. (54)
    scarcity: float  # escassez — elegíveis por vaga, média dos alunos
    contention: float  # concorrência — candidatos por vaga, média dos alunos
    mean_grade_average: float  # eq. (56)
    correlation: float  # eq. (57)
    semestralization: float  # carga aprovada / máximo possível desde o ingresso


class CourseSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course: str
    # Null no recorte do curso inteiro (`by_course`); em `by_cohort`, o
    # período de ingresso (t_a, eq. 31) da geração agregada ali.
    entry_period: int | None
    # Nulos quando o recorte não tem aluno no período — não havia ninguém, o
    # que é diferente de ninguém ter ficado satisfeito.
    metrics: MetricsOut | None
    active: int
    # Alunos do recorte que já ingressaram, tenham saído ou não — o
    # denominador das frações de formados e de jubilados.
    population: int
    graduated: int
    dismissed: int
    mean_credits: float | None
    mean_approved_hours: float | None
    credits_per_student: float | None
    credits_per_seat: float | None
    # Créditos apostados no período por aluno ativo, somando as rodadas.
    # Pode passar do orçamento: lance perdido não consome nada.
    mean_bids: float | None
    # Null nas rodadas: o retorno só existe ao fim do período, quando saem as notas.
    mean_credit_return: float | None


class PriceStatsOut(BaseModel):
    """Dispersão de pi_x (eq. 24) entre as disciplinas no mercado."""

    model_config = ConfigDict(from_attributes=True)

    min: float
    mean: float
    max: float


class RoundReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period: int
    round: int
    overall: MetricsOut
    by_course: list[CourseSnapshotOut]
    # Agregado por curso × geração; só as gerações que já ingressaram.
    by_cohort: list[CourseSnapshotOut]
    # Null quando nenhuma disciplina estava no mercado no instante.
    prices: PriceStatsOut | None


class DisciplineSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    seats: int
    filled: int
    # Média de pi_x nas rodadas em que ainda havia vaga; null se nunca houve.
    mean_price: float | None
    approvals: int


class PeriodReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period: int
    rounds: list[RoundReportOut]
    aggregate: RoundReportOut
    disciplines: list[DisciplineSnapshotOut]
    graduated_now: int
    dismissed_now: int


class StudentSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    course: str
    entry_period: int
    grade_average: float
    approved_hours: int
    hours_to_graduate: int
    credits: int
    enrollments: int
    approvals: int
    mean_satisfaction: float
    graduated_at: int | None
    dismissed_at: int | None


class RequestRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    discipline: str
    kind: Literal["required", "elective", "free"]
    utility: float
    bids: list[int]
    won_round: int | None
    paid: int
    attempt: int | None
    grade: float | None
    approved: bool
    returned: int


class StudentPeriodRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period: int
    credits_start: int
    credits_spent: int
    credits_returned: int
    credits_end: int
    satisfaction: float
    grade_average: float
    approved_hours: int
    enrolled_hours: int
    requests: list[RequestRecordOut]
    graduated: bool
    dismissed: bool


class StudentHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    periods: list[StudentPeriodRecordOut]


class SimulateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    periods: list[PeriodReportOut]
    students: list[StudentSummaryOut]
    histories: list[StudentHistoryOut]
    courses: list[str]
    disciplines: list[str]
