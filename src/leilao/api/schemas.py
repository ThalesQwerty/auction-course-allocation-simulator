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
from ..config import CreditMemory, CreditReturnPolicy, Mechanism, Resolver


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
    difficulty: float = Field(
        default=1.0,
        gt=0,
        description=(
            "D_x — quantas tentativas a disciplina custa para render o que uma de "
            "dificuldade 1 rende de primeira"
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


class ScenarioIn(BaseModel):
    """O cenário em si (Seção 7.2) — tudo que descreve a universidade e a
    população, sem dizer *como* ele será executado.

    Os dois modos partem daqui e acrescentam só o que lhes é próprio: uma
    execução única acrescenta a seed, e a comparação acrescenta quantas
    execuções fazer. É o que garante que os dois lados de uma comparação rodem
    exatamente o mesmo cenário — a condição metodológica da Seção 7.3.
    """

    disciplines: list[DisciplineIn] = Field(default_factory=list)
    # As distribuições que descrevem a população. Não há perfis: todo aluno sai
    # daqui, e a diferença entre dois alunos é só o que a seed sorteou.
    # A aptidão entra por média e concentração, que é como se lê uma
    # população; `grading.beta_shape` as converte nos dois parâmetros de forma
    # que a Beta pede. Média 0,65 com concentração 10 é a Beta(6,5, 3,5)
    # calibrada: nota média 6,5 e 84% de aprovação em dificuldade 1.
    aptitude_mean: float = Field(
        default=0.65, gt=0, lt=1, description="média da aptidão"
    )
    aptitude_concentration: float = Field(
        default=10.0, gt=0, description="concentração da aptidão em torno da média"
    )
    utility_gain: float = Field(
        default=0.0,
        ge=0,
        description=(
            "ganho por utilidade: o quanto a utilidade mexe na nota, como "
            "expoente sobre u_rel. 0 desliga e deixa a função de nota neutra "
            "entre os mecanismos; é o controle a reportar ao lado de qualquer "
            "resultado em conclusões."
        ),
    )
    utility_stability: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description=(
            "quanto do gosto do aluno é permanente, de 0 a 1. 0 resorteia a "
            "preferência inteira a cada período; 1 congela. Ortogonal ao sigma: "
            "a divisão preserva a dispersão de cada período"
        ),
    )
    retake_gain: float = Field(
        default=1.0,
        ge=0,
        description=(
            "ganho por recursada: quanta tentativa efetiva cada repetição "
            "acrescenta no denominador do expoente. 1 recupera o D/t"
        ),
    )
    utility_sigma: float = Field(
        default=0.25,
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
    resolver: Resolver = Field(
        default="ilp",
        description="quem decide a alocação: PLI global ou varredura gulosa",
    )
    credit_memory: CreditMemory = Field(
        default="carry",
        description=(
            "se o orçamento carrega entre períodos (eq. 36) ou recomeça em Gamma_min"
        ),
    )
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


class PeriodSeriesOut(BaseModel):
    """As métricas de período de uma execução, sem reduzir — o que o recorte
    por período da tela desenha.

    Listas **paralelas** e só com os períodos medidos: `period[i]` é o número do
    período a que `efficiency[i]` se refere. O primeiro período não aparece (nele
    todo mundo acabou de ingressar), e por isso o número vem explícito em vez de
    sair do índice. `students` é o peso do ponto na média ponderada, e cai à
    vista na drenagem.

    Sem tempo de formatura: é da execução inteira, e a versão por período seria
    outra grandeza, com viés de sobrevivência.
    """

    model_config = ConfigDict(from_attributes=True)

    period: list[int]
    students: list[int]
    efficiency: list[float]
    utilization: list[float]
    fidelity: list[float]
    fairness: list[float]
    correlation: list[float]
    # A saturação do período, rodada a rodada: a posição [i][r] é o que foi
    # ganho por aluno na rodada r+1 do período `period[i]`. Uma linha por
    # período medido, sempre com |R| posições.
    allocations_per_round: list[list[float | None]]


class CohortSeriesOut(BaseModel):
    """O mesmo resumo da execução, uma linha por geração — o terceiro eixo da
    tela.

    A geração é o período de ingresso (t_a), e o aluno fica nela do ingresso ao
    diploma. A redução é a mesma do agregado; o que muda é sobre quem ela corre.

    **As gerações não são intercambiáveis**: a primeira encontra uma
    universidade quase vazia e a última a encontra cheia, de modo que a
    inclinação ao longo do eixo mistura mecanismo e mercado. O que se lê com
    segurança é a comparação entre braços num mesmo ponto.

    Aqui o tempo de formatura entra — cada aluno pertence a uma geração só —, e
    vem com os concluintes, o denominador sem o qual ele não se lê: a contagem
    e a fração dela sobre quantos entraram naquela geração.
    """

    model_config = ConfigDict(from_attributes=True)

    cohort: list[int]
    graduates: list[int]
    graduation_rate: list[float]
    efficiency: list[float]
    utilization: list[float]
    fidelity: list[float]
    fairness: list[float]
    correlation: list[float]
    time_to_graduate: list[float | None]
    allocations_per_round: list[list[float | None]]


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
    # Aproveitamento: a contraparte em carga do psi, que é em utilidade.
    utilization: float
    # Fidelidade da mensagem: quanto da preferência sobrevive à tradução.
    # Descreve, não pontua — como a correlação.
    fidelity: float
    fairness: float  # eq. (55)
    correlation: float  # eq. (57)
    # Períodos do ingresso ao diploma, na média dos concluintes. Null quando
    # ninguém concluiu.
    time_to_graduate: float | None
    # Vagas obtidas por aluno em cada rodada (o índice r-1 é a rodada r), com
    # |R| posições. Mede a **saturação**: o que se lê é o decaimento entre as
    # rodadas, não o nível de cada uma.
    allocations_per_round: list[float | None]
    # As mesmas métricas de período, período a período: o material de que a
    # média ponderada saiu.
    by_period: PeriodSeriesOut
    # O mesmo resumo por geração: a mesma redução, corrida sobre outro recorte.
    by_cohort: CohortSeriesOut


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


class CompareResponse(BaseModel):
    """As amostras dos três braços, pareadas pela seed: o i-ésimo elemento de
    cada lista é a mesma população sob regras diferentes."""

    model_config = ConfigDict(from_attributes=True)

    runs: int
    arms: list[ArmResultOut]


class MetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    students: int
    allocated: int
    allocations_per_student: float
    efficiency: float  # eq. (53)
    # Aproveitamento: carga horária obtida no período ÷ W_a, média dos medidos.
    # A contraparte em carga do psi, que é em utilidade.
    utilization: float
    # Fidelidade da mensagem: cosseno entre o lance normalizado e a utilidade.
    # Mede quanto da preferência sobrevive à tradução. Descreve, não pontua.
    fidelity: float
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
    aptitude_mean: float = Field(default=0.65, gt=0, lt=1)
    aptitude_concentration: float = Field(default=10.0, gt=0)
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
