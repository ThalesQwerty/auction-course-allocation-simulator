"""O que uma simulação publica: os registros do relatório."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..metrics import Metrics

GUARANTEED_ROUND = 0


@dataclass(frozen=True)
class PriceStats:
    """Dispersão de π_x (eq. 24) entre as disciplinas num instante."""

    min: float
    mean: float
    max: float

    @classmethod
    def of(cls, prices: list[int] | list[float]) -> "PriceStats | None":
        if not prices:
            return None
        return cls(min=min(prices), mean=sum(prices) / len(prices), max=max(prices))


@dataclass(frozen=True)
class GroupSnapshot:
    """Um recorte de alunos num instante — a unidade dos gráficos."""

    group: str | None
    metrics: Metrics | None
    active: int
    population: int | None
    graduated: int | None
    dismissed: int | None
    mean_credits: float | None
    mean_approved_hours: float | None
    credits_per_student: float | None
    credits_per_seat: float | None
    mean_bids: float | None
    mean_credits_spent: float | None
    mean_credit_return: float | None


@dataclass(frozen=True)
class RoundReport:
    """Um ponto da série: uma rodada, ou o agregado de um período (`round` 0)."""

    period: int
    round: int
    overall: GroupSnapshot
    by_cohort: list[GroupSnapshot]
    prices: PriceStats | None
    allocation_seconds: float = field(compare=False)
    by_profile: dict[str, list[GroupSnapshot]] = field(default_factory=dict)
    by_cell: dict[str, list[GroupSnapshot]] = field(default_factory=dict)


@dataclass(frozen=True)
class DisciplineSnapshot:
    """O recorte da **turma**: é dela que são a vaga, o preço e a demanda."""

    name: str
    discipline: str
    curriculum_period: int
    hours: int
    classes: int
    schedule: str
    elective: bool
    seats: int
    filled: int
    granted: int
    requests: int
    mean_price: float | None
    approvals: int
    exclusions: int


@dataclass(frozen=True)
class PeriodReport:
    period: int
    rounds: list[RoundReport]
    aggregate: RoundReport
    disciplines: list[DisciplineSnapshot]
    graduated_now: int
    dismissed_now: int


@dataclass(frozen=True)
class RequestRecord:
    """O que aconteceu com uma disciplina que o aluno quis num período."""

    discipline: str
    utility: float
    bids: list[int]
    won_round: int | None
    paid: int
    excluded: bool
    attempt: int | None
    grade: float | None
    approved: bool
    returned: int


@dataclass(frozen=True)
class StudentPeriodRecord:
    """A linha do histórico de um aluno num período letivo."""

    period: int
    credits_start: int
    credits_spent: int
    credits_returned: int
    credits_end: int
    satisfaction: float
    grade_average: float
    approved_hours: int
    enrolled_hours: int
    retained_hours: int
    effective_load: int
    requests: list[RequestRecord]
    graduated: bool


@dataclass(frozen=True)
class StudentHistory:
    """Só os períodos em que o aluno participou da matrícula: quem já se"""

    student_id: str
    periods: list[StudentPeriodRecord]


@dataclass(frozen=True)
class StudentSummary:
    id: str
    name: str
    entry_period: int
    availability_anchor: float
    selectivity_anchor: float
    grade_average: float
    approved_hours: int
    hours_to_graduate: int
    credits: int
    enrollments: int
    approvals: int
    mean_satisfaction: float
    graduated_at: int | None
    dismissed_at: int | None


@dataclass(frozen=True)
class SimulationResult:
    periods: list[PeriodReport] = field(default_factory=list)
    students: list[StudentSummary] = field(default_factory=list)
    histories: list[StudentHistory] = field(default_factory=list)
    disciplines: list[str] = field(default_factory=list)
    classes: dict[str, str] = field(default_factory=dict)
    curriculum_periods: dict[str, int] = field(default_factory=dict)
    interest_distribution: list[float] = field(default_factory=list)
    grade_distribution: list[float] = field(default_factory=list)
    warmup_periods: int = 0

    @property
    def observed(self) -> list[PeriodReport]:
        """Os períodos **medidos** — os de depois da pré-população."""
        return [p for p in self.periods if p.period > self.warmup_periods]
