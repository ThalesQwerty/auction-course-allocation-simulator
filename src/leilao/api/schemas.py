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
from ..config import CreditReturnPolicy, Mechanism


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
    unlocks: list[str] = Field(
        default_factory=list,
        description="sucessores — disciplinas que esta desbloqueia. Vazio = terminal.",
    )
    entry: bool = Field(
        default=False,
        description="matrícula garantida de quem ingressa; não pode ter pré-requisito",
    )
    elective: bool = Field(
        default=False,
        description=(
            "optativa: sem pré-requisito, não é pré-requisito de ninguém, e fica fora "
            "da matrícula garantida. Concluir exige somar `elective_hours` entre as "
            "optativas aprovadas, e não aprovar em cada uma."
        ),
    )


class ScenarioIn(BaseModel):
    """O cenário em si (Seção 7.2) — tudo que descreve a universidade e a
    população, sem dizer *como* ele será executado.

    Os dois modos partem daqui e acrescentam só o que lhes é próprio: uma
    execução única acrescenta a seed, e a comparação acrescenta quantas
    execuções fazer. É o que garante que os dois lados de uma comparação rodem
    exatamente o mesmo cenário — a condição metodológica da Seção 7.3.
    """

    disciplines: list[DisciplineIn] = Field(default_factory=list)
    # As duas normais que descrevem a população. Não há perfis: todo aluno sai
    # daqui, e a diferença entre dois alunos é só o que a seed sorteou.
    grade_mean: float = Field(default=6.5, ge=0, le=10, description="média das notas")
    grade_stddev: float = Field(default=1.5, gt=0, description="desvio padrão das notas")
    learning_gain: float = Field(
        default=2.5, gt=0, le=10, description="ganho de nota por recursada — eq. (33)"
    )
    utility_sigma: float = Field(
        default=1.0,
        gt=0,
        description=(
            "desvio da log-normal de onde saem os valores preliminares da matriz de "
            "utilidades. Controla o quanto o aluno diferencia as disciplinas: "
            "**grande concentra** (quer uma ou duas e despreza o resto), pequeno "
            "achata. A média do logaritmo é fixa em 0 porque some na normalização. "
            "A faixa útil cabe entre ~0,25 e ~3."
        ),
    )
    max_hours: int = Field(
        default=360, ge=1, description="W_a — carga horária máxima por período"
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
            "Não pode passar da menor oferta entre as disciplinas de entrada, porque "
            "o ingressante tem vaga garantida em todas elas."
        ),
    )
    rounds: int = Field(default=1, ge=1, le=10, description="|R| — rodadas por período")
    min_grade: float = Field(default=5.0, gt=0, le=10, description="n_min")
    elective_hours: int = Field(
        default=0,
        ge=0,
        description="X — carga horária optativa exigida para concluir",
    )
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


class SweepIn(BaseModel):
    """A varredura da forma da preferência, o segundo eixo da comparação.

    Os sigmas saem de uma faixa **linear** — passos iguais do mínimo ao máximo.
    Linear basta porque o coeficiente de variação da log-normal cresce depressa
    em sigma: a faixa útil inteira cabe entre ~0,25 e ~3.

    O `utility_sigma` do cenário é o **canônico**, medido pelo boxplot com mais
    execuções. Ele não precisa cair exatamente num ponto varrido — a interface o
    marca como referência no eixo.
    """

    min_sigma: float = Field(
        default=0.25, gt=0, le=20, description="menor sigma da faixa"
    )
    max_sigma: float = Field(
        default=3.0, gt=0, le=20, description="maior sigma da faixa"
    )
    points: int = Field(
        default=12, ge=2, le=41, description="quantos sigmas, em passos iguais"
    )
    runs: int = Field(
        default=3,
        ge=1,
        le=MAX_RUNS,
        description=(
            "execuções por ponto. Poucas de propósito: aqui se lê a forma da "
            "curva ao longo de k, não a significância num k — essa é a pergunta "
            "do boxplot, que roda no k canônico com `runs`."
        ),
    )


class CompareRequest(ScenarioIn):
    """Uma comparação entre os três modelos sobre o mesmo cenário.

    Dois campos do cenário não têm efeito aqui. A **seed**, porque as seeds são
    1..`runs` e cada uma roda nos três braços: fixar uma só mediria aquela
    população, e não parear mediria a variação entre populações junto da
    variação entre modelos. E o **retorno de créditos**, porque ele é o eixo do
    experimento — um braço o usa proporcional e o outro não o usa.
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
    sweep: SweepIn | None = Field(
        default=None,
        description=(
            "quando presente, roda também a varredura da forma da preferência e "
            "devolve um ponto por k. Omitir deixa só o k canônico."
        ),
    )


class RunSummaryOut(BaseModel):
    """Uma execução reduzida a um ponto por métrica — o que vira um valor no
    boxplot. As três de período são a média ponderada pelos alunos medidos, de
    modo que a fase de drenagem não pese como um período cheio; o tempo de
    formatura é da execução inteira."""

    model_config = ConfigDict(from_attributes=True)

    seed: int
    # Períodos efetivamente publicados; menor que |T| se a população se esvaziou
    # antes do horizonte.
    periods: int
    # Concluintes da execução — o contexto sem o qual `time_to_graduate` não se
    # lê: quem forma menos pode exibir um tempo menor só por sobrarem os rápidos.
    graduates: int
    efficiency: float  # eq. (53)
    fairness: float  # eq. (55)
    correlation: float  # eq. (57)
    # Períodos do ingresso ao diploma, na média dos concluintes. Null quando
    # ninguém concluiu.
    time_to_graduate: float | None
    # Vagas obtidas por aluno em cada rodada (o índice r-1 é a rodada r), com
    # |R| posições. Mede a **saturação**: o que se lê é o decaimento entre as
    # rodadas, não o nível de cada uma.
    allocations_per_round: list[float | None]


class ArmResultOut(BaseModel):
    """Um dos modelos comparados e as suas N execuções.

    `key` é o identificador estável da série; o rótulo em português é da
    interface, não da API.
    """

    model_config = ConfigDict(from_attributes=True)

    key: str
    mechanism: Mechanism
    credit_return: CreditReturnPolicy
    runs: list[RunSummaryOut]


class SweepPointOut(BaseModel):
    """Um ponto da varredura: a comparação inteira num desvio de preferência.

    `distribution` é o histograma de como a utilidade se reparte dentro da linha
    de um aluno naquele sigma — o gráfico da causa, ao lado do do resultado.
    Cada linha é reescalada ao próprio [mínimo, máximo] e dividida em faixas de
    mesma largura; as frações somam 1.
    """

    model_config = ConfigDict(from_attributes=True)

    sigma: float
    arms: list[ArmResultOut]
    distribution: list[float]


class SweepOut(BaseModel):
    """A varredura inteira, em ordem crescente de sigma. `canonical` é o
    `utility_sigma` do cenário, que o boxplot mede com mais execuções — ele não
    precisa cair num ponto varrido."""

    model_config = ConfigDict(from_attributes=True)

    canonical: float
    runs: int
    points: list[SweepPointOut]


class CompareResponse(BaseModel):
    """As amostras dos três braços, pareadas pela seed: o i-ésimo elemento de
    cada lista é a mesma população sob regras diferentes."""

    model_config = ConfigDict(from_attributes=True)

    runs: int
    arms: list[ArmResultOut]
    # Presente só quando a requisição pediu a varredura.
    sweep: SweepOut | None = None
    # As duas distribuições de entrada do cenário, como histogramas. Não variam
    # entre braços nem entre seeds — são do cenário, não da execução.
    utility_distribution: list[float] = []
    grade_distribution: list[float] = []


class MetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    students: int
    allocated: int
    allocations_per_student: float
    efficiency: float  # eq. (53)
    # Aproveitamento: carga horária obtida no período ÷ W_a, média dos medidos.
    # A contraparte em carga do psi, que é em utilidade.
    utilization: float
    fairness: float  # eq. (55)
    occupancy: float  # eq. (54)
    scarcity: float  # escassez — elegíveis por vaga, média dos alunos
    contention: float  # concorrência — candidatos por vaga, média dos alunos
    mean_grade_average: float  # eq. (56)
    correlation: float  # eq. (57)
    semestralization: float  # carga aprovada / máximo possível desde o ingresso


class GroupSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Quem é este recorte: null na universidade inteira (`overall`) e o período
    # de ingresso (t_a, eq. 31) em `by_cohort`. Texto, e não inteiro, porque o
    # eixo é genérico; a lista de origem diz como ler a chave.
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
    # As duas distribuições de entrada do cenário, como histogramas: uma fração
    # por faixa, somando 1. As utilidades são reescaladas por linha e vão de 0 a
    # 1; as notas vão de 0 a 10.
    utility_distribution: list[float] = []
    grade_distribution: list[float] = []


class PlaygroundDisciplineIn(BaseModel):
    name: str
    seats: int = Field(ge=0)
    hours: int = Field(gt=0)


class PlaygroundStudentIn(BaseModel):
    id: str
    credits: int = Field(default=0, ge=0)
    cr: float = 0
    max_hours: int = Field(gt=0)
    utilities: dict[str, float]
    eligible: list[str]


class PlaygroundRequest(BaseModel):
    mechanism: Mechanism
    rounds: int = Field(ge=1, le=10)
    seed: int = 0
    grade_mean: float = Field(ge=0, le=10)
    grade_stddev: float = Field(gt=0)
    disciplines: list[PlaygroundDisciplineIn]
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
    discipline: str
    grade: float


class PlaygroundResponse(BaseModel):
    rounds: list[PlaygroundRoundOut]
    grades: list[PlaygroundGradeOut]
