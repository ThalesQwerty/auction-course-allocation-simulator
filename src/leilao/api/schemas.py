"""Schemas Pydantic para a API — o corpo da requisição já É o cenário completo
(sem persistência): a interface monta tudo no navegador e manda de uma vez.

São duas entradas: `/run` recebe um leilão isolado (agentes, bens e lances
explícitos) e `/simulate` recebe a configuração de uma simulação multi-período
completa, em que alunos, utilidades e notas são gerados a partir da seed.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..auction import AuctionResult
from ..comparison import MAX_RUNS
from ..config import MAX_AFFINITY_INTENSITY, AffinityKind, CreditReturnPolicy


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
    prerequisites: list[str] = Field(
        default_factory=list,
        description=(
            "disciplinas que precisam estar aprovadas para o aluno disputar vaga aqui. "
            "Vazio = disciplina de 1º período, em que o ingressante entra direto."
        ),
    )


class AptitudeProfileIn(BaseModel):
    """Perfil de aptidão: a normal das notas de primeira tentativa."""

    name: str
    mean: float = Field(ge=0, le=10, description="média das notas")
    stddev: float = Field(gt=0, description="desvio padrão das notas")
    learning_gain: float = Field(
        default=2.5, gt=0, le=10, description="ganho de nota por recursada — eq. (33)"
    )
    share: float = Field(gt=0, le=100, description="% dos alunos com este perfil")


class AffinityProfileIn(BaseModel):
    """Perfil de afinidade: o expoente aplicado à matriz de utilidades."""

    name: str
    kind: AffinityKind = Field(
        description=(
            "'concentrated' eleva a um inteiro positivo e afasta as utilidades entre "
            "si; 'diluted' eleva ao inverso dele e as aproxima"
        )
    )
    intensity: int = Field(
        ge=1, le=MAX_AFFINITY_INTENSITY, description="intensidade, inteiro positivo"
    )
    max_hours: int = Field(
        default=360, ge=1, description="W_a — carga horária máxima por período"
    )
    share: float = Field(gt=0, le=100, description="% dos alunos com este perfil")


class ScenarioIn(BaseModel):
    """O cenário em si (Seção 7.2) — tudo que descreve a universidade e a
    população, sem dizer *como* ele será executado.

    Os dois modos partem daqui e acrescentam só o que lhes é próprio: uma
    execução única acrescenta a seed, e a comparação acrescenta quantas
    execuções fazer. É o que garante que os dois lados de uma comparação rodem
    exatamente o mesmo cenário — a condição metodológica da Seção 7.3.
    """

    disciplines: list[DisciplineIn] = Field(default_factory=list)
    aptitude_profiles: list[AptitudeProfileIn] = Field(
        default_factory=list,
        description=(
            "perfis de aptidão; as fatias precisam somar 100%. Vazio = um perfil "
            "neutro para toda a população."
        ),
    )
    affinity_profiles: list[AffinityProfileIn] = Field(
        default_factory=list,
        description=(
            "perfis de afinidade; as fatias precisam somar 100%. Vazio = um perfil "
            "neutro (expoente 1, sem distorção). É independente da aptidão: a fatia "
            "de uma combinação é o produto das duas."
        ),
    )
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
    students_per_period: int = Field(
        default=1,
        ge=1,
        description=(
            "alunos que ingressam em cada período com ingresso; a população é isto × L. "
            "Não pode passar da menor oferta entre as disciplinas de 1º período, porque "
            "o ingressante tem vaga garantida em todas elas."
        ),
    )
    rounds: int = Field(default=1, ge=1, le=10, description="|R| — rodadas por período")
    min_grade: float = Field(default=5.0, gt=0, le=10, description="n_min")
    base_credits: int = Field(default=10, ge=1, description="Gamma_min — créditos base")
    # f_gamma — eq. (34); as políticas estão em `grading.credit_return`.
    # Este e o `base_credits` acima são do leilão por créditos e não têm efeito
    # na linha de base por CR, que não tem orçamento nem preço pago.
    credit_return: CreditReturnPolicy = "none"


class SimulateRequest(ScenarioIn):
    """Uma execução única do mecanismo proposto."""

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


class CompareRequest(ScenarioIn):
    """Uma comparação entre os dois mecanismos sobre o mesmo cenário.

    Não há seed: as seeds são 1..`runs`, e cada uma roda dos dois lados. Fixar
    uma só mediria aquela população; não parear mediria a variação entre
    populações junto da variação entre mecanismos.
    """

    runs: int = Field(
        default=20,
        ge=1,
        le=MAX_RUNS,
        description=(
            "N — quantas simulações de cada mecanismo, com as seeds de 1 a N. "
            "São 2N simulações no total, e a seed pareia os dois lados."
        ),
    )


class RunSummaryOut(BaseModel):
    """Uma execução reduzida a um ponto por métrica — o que vira um valor no
    boxplot. É a média dos períodos ponderada pelos alunos ativos, de modo que
    a fase de drenagem não pese como um período cheio."""

    model_config = ConfigDict(from_attributes=True)

    seed: int
    # Períodos efetivamente publicados; menor que |T| se a população se esvaziou
    # antes do horizonte.
    periods: int
    efficiency: float  # eq. (53)
    fairness: float  # eq. (55)
    correlation: float  # eq. (57)
    occupancy: float  # eq. (54)
    semestralization: float


class CompareResponse(BaseModel):
    """As duas amostras, pareadas pela seed: o i-ésimo elemento de cada lista é
    a mesma população sob regras de alocação diferentes."""

    model_config = ConfigDict(from_attributes=True)

    runs: int
    credits: list[RunSummaryOut]
    ranking: list[RunSummaryOut]


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


class GroupSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Quem é este recorte: null na universidade inteira (`overall`), o período
    # de ingresso (t_a, eq. 31) em `by_cohort` e o nome do perfil em
    # `by_aptitude`/`by_affinity`. Texto porque os três eixos dividem a mesma
    # estrutura; a lista de origem diz como ler a chave.
    group: str | None
    # Nulos quando o recorte não tem aluno no período — não havia ninguém, o
    # que é diferente de ninguém ter ficado satisfeito.
    metrics: MetricsOut | None
    active: int
    # Alunos do recorte que já ingressaram, tenham saído ou não — o
    # denominador da fração de formados.
    population: int
    graduated: int
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
    overall: GroupSnapshotOut
    # Agregado por geração; só as gerações que já ingressaram.
    by_cohort: list[GroupSnapshotOut]
    # E pelos dois eixos de perfil, na ordem em que o cenário os declara. Os
    # três recortes particionam a mesma população: somar qualquer um deles
    # reproduz `overall`.
    by_aptitude: list[GroupSnapshotOut]
    by_affinity: list[GroupSnapshotOut]
    # Null quando nenhuma disciplina estava no mercado no instante.
    prices: PriceStatsOut | None


class DisciplineSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    # Período da disciplina na grade, induzido dos pré-requisitos.
    curriculum_period: int
    hours: int
    seats: int
    filled: int
    # Vagas entregues à matrícula garantida dos ingressantes, antes do leilão.
    granted: int
    # Quantos pediram a disciplina no período; dividido por `seats` dá a
    # concorrência dela.
    requests: int
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


class StudentSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    entry_period: int
    aptitude: str
    affinity: str
    grade_average: float
    approved_hours: int
    hours_to_graduate: int
    credits: int
    enrollments: int
    approvals: int
    mean_satisfaction: float
    graduated_at: int | None


class RequestRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    discipline: str
    utility: float
    bids: list[int]
    # 0 = vaga garantida de ingressante, concedida fora do leilão.
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


class StudentHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    periods: list[StudentPeriodRecordOut]


class SimulateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    periods: list[PeriodReportOut]
    students: list[StudentSummaryOut]
    histories: list[StudentHistoryOut]
    disciplines: list[str]
    # Período de cada disciplina na grade, induzido dos pré-requisitos.
    curriculum_periods: dict[str, int]
    # Os perfis do cenário, na ordem em que `by_aptitude` e `by_affinity` saem.
    aptitude_profiles: list[str]
    affinity_profiles: list[str]
