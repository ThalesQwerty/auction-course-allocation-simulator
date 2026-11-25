"""Schemas Pydantic para a API — o corpo da requisição já É o cenário completo"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..auction import AuctionResult
from ..comparison import ARMS, MAX_RUNS
from ..config import (
    AvailabilityShape,
    Mechanism,
    MAX_CUTS,
    horizon_for_window,
)


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
    classes: int = Field(
        ge=0,
        description=(
            "turmas ofertadas; as vagas são `classes × class_size` — ver "
            "`ScenarioIn.class_size`"
        ),
    )
    hours: int = Field(gt=0, description="w_x — carga horária")
    unlocks: list[str] = Field(
        default_factory=list,
        description="sucessores — disciplinas que esta desbloqueia. Vazio = terminal.",
    )
    entry: bool = Field(
        default=False,
        description="matrícula garantida de quem ingressa; não pode ter pré-requisito",
    )
    stability: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "quanto do gosto por esta disciplina é permanente; nulo cai no valor "
            "do cenário. Declarar por disciplina sincroniza a persistência entre "
            "concorrentes, que é o que trava a fila"
        ),
    )
    elective: bool = Field(
        default=False,
        description=(
            "optativa: sem pré-requisito, não é pré-requisito de ninguém, e fica fora "
            "da matrícula garantida. Concluir exige somar `elective_hours` entre as "
            "optativas aprovadas, e não aprovar em cada uma."
        ),
    )


class AvailabilityIn(BaseModel):
    """A distribuição de disponibilidade da população — **uma só**."""

    model_config = ConfigDict(from_attributes=True)

    mode_hours: float = Field(default=306.0, gt=0)
    full_load_rate: float = Field(default=0.10, gt=0, lt=1)

    def to_shape(self) -> AvailabilityShape:
        return AvailabilityShape(
            mode_hours=self.mode_hours, full_load_rate=self.full_load_rate
        )


class ScenarioIn(BaseModel):
    """O cenário em si (Seção 7.2) — tudo que descreve a universidade e a"""

    disciplines: list[DisciplineIn] = Field(default_factory=list)
    class_size: int = Field(
        default=25, gt=0, description="alunos por turma — q_x = classes × este"
    )
    approval_rate: float = Field(
        default=0.7,
        gt=0,
        lt=1,
        description=(
            "P_apr — a probabilidade de a nota alcançar n_min. Parâmetro global: "
            "não há heterogeneidade de desempenho, e o quantil da nota é sorteado "
            "de novo a cada tentativa"
        ),
    )
    grade_sd: float = Field(
        default=2.0,
        gt=0,
        description="σ — o desvio padrão das notas; a média sai dele e de P_apr",
    )
    repetition_gain: float = Field(
        default=1.0,
        ge=0,
        description=(
            "ω — o ganho por repetição: quanto de experiência cada recursada "
            "acrescenta. Em 0 repetir não ajuda; em 1 cada tentativa soma uma "
            "unidade ao denominador do expoente"
        ),
    )
    schedule_sigma: float = Field(
        default=0.6,
        ge=0,
        description=(
            "σ do interesse por horário, a segunda metade do produto que forma o "
            "interesse por turma. Em 0 todas as turmas de uma disciplina valem "
            "igual"
        ),
    )
    first_seed: int = Field(
        default=1,
        ge=0,
        description=(
            "a seed da primeira simulação da comparação; as seguintes contam de "
            "1 em 1 a partir dela"
        ),
    )
    availability: AvailabilityIn = Field(
        default_factory=AvailabilityIn,
        description=(
            "distribuição de disponibilidade: governa a log-normal das horas "
            "que o aluno tem para o período, sorteada a cada período"
        ),
    )
    availability_stability: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description=(
            "quanto da disponibilidade é permanente — a correlação entre dois "
            "períodos do mesmo aluno"
        ),
    )
    selectivity_median: float = Field(
        default=0.0035,
        ge=0,
        description=(
            "a mediana da seletividade, na **escala do interesse**: quanto "
            "vale, para o aluno, não estudar. A reserva dele é `S / (S + ΣI)` "
            "sobre o interesse das elegíveis. 0 é o especulador"
        ),
    )
    selectivity_sigma: float = Field(
        default=0.6, gt=0, description="desvio em log da seletividade"
    )
    grade_cuts: list[float] = Field(
        default=[5.0, 7.0],
        max_length=MAX_CUTS,
        description="pontos de corte do recorte por CR, em [0, 10]",
    )
    reserve_cuts: list[float] = Field(
        default=[0.01, 0.03],
        max_length=MAX_CUTS,
        description="pontos de corte do recorte por utilidade de reserva, em [0, 1)",
    )
    students_per_entry_class: int = Field(
        default=10,
        ge=1,
        description=(
            "quantos ingressantes entram em cada turma de disciplina de "
            "entrada, no máximo `class_size`. A coorte é isto vezes as turmas "
            "de uma disciplina de entrada, e em regime a população é a coorte "
            "vezes o prazo de jubilamento"
        ),
    )
    slots: int = Field(
        default=12,
        ge=1,
        le=48,
        description=(
            "quantos horários existem. Cada horário é um grupo de exclusão "
            "mútua entre turmas, e as turmas da grade são repartidas entre eles "
            "circularmente. O piso é o maior número de turmas de uma disciplina"
        ),
    )
    interest_stability: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description=(
            "quanto do interesse do aluno é permanente, de 0 a 1. 0 resorteia o "
            "interesse inteiro a cada período; 1 congela. Ortogonal ao sigma: "
            "a divisão preserva a dispersão de cada período"
        ),
    )
    interest_mean: float = Field(
        default=1.0,
        allow_inf_nan=False,
        description=(
            "μ — média do logaritmo da log-normal de onde sai o interesse. Não "
            "mexe em alocação nenhuma: multiplica a linha por e^μ, e a "
            "normalização desfaz o fator. Existe para a prévia da log-normal "
            "fonte se ler em escala confortável. A atratividade soma-se a ela."
        ),
    )
    interest_sigma: float = Field(
        default=1.0,
        gt=0,
        description=(
            "σ — desvio do logaritmo da log-normal de onde sai o interesse — o "
            "sorteio que, normalizado sobre a grade e visto pelo histórico do "
            "aluno, vira a utilidade. Controla o quanto o aluno diferencia as "
            "disciplinas: **grande concentra** (quer uma ou duas e despreza o "
            "resto), pequeno achata. A faixa útil cabe entre ~0,25 e ~3."
        ),
    )
    max_hours: int = Field(
        default=24, ge=1, description="W_a — carga horária máxima por período"
    )
    max_residence: int = Field(
        default=12,
        ge=1,
        le=40,
        description=(
            "períodos que o aluno tem para concluir, contados do ingresso. Quem chega "
            "ao fim do último sem fechar a grade é jubilado e sai da simulação. É "
            "também o tamanho da pré-população, porque a população só fica constante "
            "a partir dele"
        ),
    )

    @property
    def warmup_periods(self) -> int:
        """A pré-população — **é** o prazo de jubilamento."""
        return self.max_residence

    @property
    def periods(self) -> int:
        """|T|, derivado — ver `config.horizon_for_window`."""
        return horizon_for_window(max_residence=self.max_residence)
    rounds: int = Field(default=1, ge=1, le=10, description="|R| — rodadas por período")
    min_grade: float = Field(default=5.0, gt=0, le=10, description="n_min")
    elective_hours: int = Field(
        default=0,
        ge=0,
        description="X — carga horária optativa exigida para concluir",
    )
    min_credits: int = Field(
        default=12, ge=1, description="C_min — orçamento mínimo do período"
    )
    max_credits: int | None = Field(
        default=30,
        ge=1,
        description="C_max — orçamento máximo do período; nulo desliga o teto",
    )


class CompareRequest(ScenarioIn):
    """Uma comparação entre os dois modelos sobre o mesmo cenário."""

    runs: int = Field(
        default=20,
        ge=1,
        le=MAX_RUNS,
        description=(
            "N — quantas simulações de cada mecanismo, com as seeds de 1 a N. "
            "São N × |arms| simulações no total, e a seed pareia os braços."
        ),
    )
    arms: list[str] = Field(
        default_factory=lambda: [arm.key for arm in ARMS],
        min_length=1,
        description=(
            "Quais braços rodar. O padrão são os dois do trabalho — "
            "`ranking_greedy` (ordenação por CR) e `credits_return` (leilão "
            "com PLI, acúmulo e retorno). Rodar um só custa metade do tempo e "
            "serve para calibrar cenário; os painéis que comparam o ausente "
            "simplesmente não aparecem."
        ),
    )


class GroupBandsOut(BaseModel):
    """Um grupo de um recorte reduzido entre as seeds, ponto a ponto."""

    model_config = ConfigDict(from_attributes=True)

    group: str
    x: list[int]
    n: list[int]
    values: dict[str, list[tuple[float, float, float] | None]]


class AxisBandsOut(BaseModel):
    """Os grupos de um recorte espacial sob uma régua do eixo X."""

    model_config = ConfigDict(from_attributes=True)

    ruler: str
    axis: str
    groups: list[GroupBandsOut]


class RunSummaryOut(BaseModel):
    """Uma simulação reduzida a um ponto por métrica — o que vira uma linha"""

    model_config = ConfigDict(from_attributes=True)

    seed: int
    periods: int
    graduates: int
    dismissed: int
    population: int
    efficiency: float
    attendance: float | None
    mean_round: float | None
    progress: float
    fidelity: float
    fairness: float
    exclusion_rate: float
    grade_average: float = 0.0
    request_states: RequestStatesOut
    time_to_graduate: float | None
    allocations_per_round: list[float | None]


class ClassPriceBandsOut(BaseModel):
    """O preço médio da turma sob um recorte da **oferta**."""

    model_config = ConfigDict(from_attributes=True)

    axis: str
    groups: list[GroupBandsOut]


class ArmResultOut(BaseModel):
    """Um dos modelos comparados e as suas N simulações."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    mechanism: Mechanism
    runs: list[RunSummaryOut]
    series: list[AxisBandsOut]
    allocation_seconds: list[list[float]] = []
    class_prices: list[ClassPriceBandsOut] = []


class CompareResponse(BaseModel):
    saved_to: str | None = None
    """As amostras dos três braços, pareadas pela seed: o i-ésimo elemento de
    cada lista é a mesma população sob regras diferentes."""

    model_config = ConfigDict(from_attributes=True)

    runs: int
    arms: list[ArmResultOut]


class RequestStatesOut(BaseModel):
    """Os seis estados de solicitação, em **média por aluno**."""

    model_config = ConfigDict(from_attributes=True)

    not_eligible: float
    not_requested: float
    refused: float
    excluded: float
    failed: float
    approved: float


class MetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    students: int
    allocated: int
    allocations_per_student: float
    efficiency: float
    attendance: float | None
    attendance_students: int | None
    progress: float
    fidelity: float
    fairness: float
    excluded: int | None
    exclusion_rate: float | None
    request_states: RequestStatesOut | None
    scarcity: float
    contention: float
    mean_grade_average: float
    semestralization: float


class GroupSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group: str | None
    metrics: MetricsOut | None
    active: int
    population: int
    graduated: int
    dismissed: int
    mean_credits: float | None
    mean_approved_hours: float | None
    credits_per_student: float | None
    credits_per_seat: float | None
    mean_bids: float | None
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
    overall: GroupSnapshotOut
    by_cohort: list[GroupSnapshotOut]
    prices: PriceStatsOut | None


class DisciplineSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    discipline: str
    curriculum_period: int
    hours: int
    seats: int
    filled: int
    granted: int
    requests: int
    mean_price: float | None
    approvals: int
    exclusions: int


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


class RequestRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    retained_hours: int
    effective_load: int
    requests: list[RequestRecordOut]
    graduated: bool


class StudentHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    periods: list[StudentPeriodRecordOut]


class TraceRequest(ScenarioIn):
    """O traço de **uma** simulação da comparação: o cenário mais o par"""

    arm: str = Field(
        description="chave do modelo, como em `/compare` — ex.: `credits_return`"
    )
    seed: int = Field(
        default=1,
        ge=1,
        description="qual simulação daquele braço — a mesma seed que o resumo traz",
    )


class TracePeriodOut(BaseModel):
    """O contexto de mercado de um período: a oferta disciplina a disciplina."""

    model_config = ConfigDict(from_attributes=True)

    period: int
    disciplines: list[DisciplineSnapshotOut]


class TraceResponse(BaseModel):
    """Uma simulação inteira, aluno a aluno — a tela de depuração do projeto."""

    model_config = ConfigDict(from_attributes=True)

    arm: str
    seed: int
    periods: list[TracePeriodOut]
    students: list[StudentSummaryOut]
    histories: list[StudentHistoryOut]
    disciplines: list[str]
    classes: dict[str, str]
    curriculum_periods: dict[str, int]


class PlaygroundClassIn(BaseModel):
    name: str
    seats: int = Field(ge=0)
    hours: int = Field(gt=0)
    discipline: str | None = None


class PlaygroundStudentIn(BaseModel):
    id: str
    credits: int = Field(default=0, ge=0)
    cr: float = 0
    max_hours: int = Field(gt=0)
    utilities: dict[str, float]
    eligible: list[str]
    availability: int | None = Field(default=None, ge=0)
    selectivity: float = Field(default=0.0, ge=0)


class PlaygroundRequest(BaseModel):
    mechanism: Mechanism
    rounds: int = Field(ge=1, le=10)
    seed: int = 0
    approval_rate: float = Field(default=0.7, gt=0, lt=1)
    grade_sd: float = Field(default=2.0, gt=0)
    classes: list[PlaygroundClassIn]
    students: list[PlaygroundStudentIn]


class PlaygroundRoundStudentOut(BaseModel):
    id: str
    bids: dict[str, int]
    utilities: dict[str, float]
    won: list[str]
    remaining_hours: int
    remaining_credits: int | None


class PlaygroundRoundOut(BaseModel):
    number: int
    prices: dict[str, int] | None
    students: list[PlaygroundRoundStudentOut]


class PlaygroundGradeOut(BaseModel):
    student_id: str
    name: str
    grade: float


class PlaygroundClosingOut(BaseModel):
    student_id: str
    load: int | None
    retained: list[str]
    excluded: list[str]


class PlaygroundResponse(BaseModel):
    rounds: list[PlaygroundRoundOut]
    closing: list[PlaygroundClosingOut]
    grades: list[PlaygroundGradeOut]
