"""Schemas Pydantic para a API — o corpo da requisição já É o cenário completo
(sem persistência): a interface monta tudo no navegador e manda de uma vez.

São três entradas: `/run` recebe um leilão isolado (agentes, bens e lances
explícitos), `/compare` recebe o cenário de uma comparação — a universidade e a
população, de que alunos, utilidades e notas saem pela seed — e `/trace` recebe
o mesmo cenário mais o par `(braço, seed)` de uma das simulações que ela rodou.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..auction import AuctionResult
from ..comparison import ARMS, MAX_RUNS
from ..config import (
    AvailabilityShape,
    CreditMemory,
    Mechanism,
    MAX_QUANTILES,
    PerformanceShape,
    Resolver,
    horizon_for_window,
)
from ..equations import grade_shape


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
    difficulty: float = Field(
        default=1.0,
        gt=0,
        description=(
            "a dificuldade, em quantas tentativas a disciplina custa para render "
            "o que uma de "
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


class PerformanceIn(BaseModel):
    """A distribuição de desempenho da população — **uma só**.

    A nota sai de uma normal dividida censurada em [0, 10], descrita pelas três
    grandezas que se leem: **nota mais provável, chance de tirar 0 e chance de
    tirar 10**. A moda é a locação, e o número digitado é literalmente o pico
    da curva. `equations.grade_shape` converte na trinca de forma.

    As três valem para a **disciplina de dificuldade 1 na primeira tentativa**;
    a dificuldade e a recursada transformam as duas chances.
    """

    model_config = ConfigDict(from_attributes=True)

    mode_grade: float = Field(default=8.0, ge=0, le=10)
    zero_rate: float = Field(default=0.005, gt=0, lt=1)
    max_rate: float = Field(default=0.008, gt=0, lt=1)

    @model_validator(mode="after")
    def _shape_exists(self) -> "PerformanceIn":
        try:
            self.to_shape().shape
        except ValueError as erro:
            raise ValueError(str(erro)) from erro
        return self

    def to_shape(self) -> PerformanceShape:
        return PerformanceShape(
            mode_grade=self.mode_grade,
            zero_rate=self.zero_rate,
            max_rate=self.max_rate,
        )


class AvailabilityIn(BaseModel):
    """A distribuição de disponibilidade da população — **uma só**.

    Duas grandezas: a **moda** em horas e a **chance de alcançar a carga
    máxima**. A segunda referencia W_a, que é do cenário.
    """

    model_config = ConfigDict(from_attributes=True)

    mode_hours: float = Field(default=306.0, gt=0)
    full_load_rate: float = Field(default=0.10, gt=0, lt=1)

    def to_shape(self) -> AvailabilityShape:
        return AvailabilityShape(
            mode_hours=self.mode_hours, full_load_rate=self.full_load_rate
        )


class ScenarioIn(BaseModel):
    """O cenário em si (Seção 7.2) — tudo que descreve a universidade e a
    população, sem dizer *como* ele será executado.

    Os dois modos partem daqui e acrescentam só o que lhes é próprio: uma
    simulação única acrescenta a seed, e a comparação acrescenta quantas
    simulações fazer. É o que garante que os dois lados de uma comparação rodem
    exatamente o mesmo cenário — a condição metodológica da Seção 7.3.
    """

    disciplines: list[DisciplineIn] = Field(default_factory=list)
    # A grade declara **turmas**; quantos cabem em cada uma é do cenário, e é
    # o botão de estresse: a mesma grade sob 20 ou 40 por turma é o mesmo
    # currículo com o dobro de aperto. Multiplicar aqui, e não na grade, é o
    # que mantém a oferta como estrutura e a lotação como tratamento.
    class_size: int = Field(
        default=25, gt=0, description="alunos por turma — q_x = classes × este"
    )
    # Os **três eixos da população**, cada um uma distribuição só mais um
    # nível basilar: a fração da variância que é permanente do aluno. Sem ele
    # o eixo descreve o sorteio do período, não um tipo de aluno, e o corte
    # por quantil fatiaria ruído.
    performance: PerformanceIn = Field(
        default_factory=PerformanceIn,
        description=(
            "distribuição de desempenho: governa a normal dividida da nota, por "
            "nota mais provável, chance de tirar 0 e chance de tirar 10"
        ),
    )
    performance_stability: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description=(
            "quanto do desempenho é do aluno e não da matéria — a correlação "
            "entre os quantis dele em duas disciplinas. Em 0 a dispersão do CR "
            "entre alunos não tem piso e a ordenação por CR vira sorte"
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
    selectivity_stability: float = Field(
        default=0.7,
        ge=0,
        le=1,
        description="quanto da seletividade é permanente, entre períodos",
    )
    quantiles: int = Field(
        default=3,
        ge=1,
        le=MAX_QUANTILES,
        description=(
            "em quantas faixas os relatórios recortam a população. O corte é "
            "sobre o nível basilar de cada eixo; em 1 há uma faixa só"
        ),
    )
    students_per_period: int = Field(
        default=90,
        ge=1,
        description=(
            "quantos alunos ingressam por período. Em regime a população é "
            "isto vezes o prazo de jubilamento"
        ),
    )
    class_stability: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description=(
            "quanto do interesse é comum às turmas da mesma disciplina. Em 1 "
            "todas valem o mesmo para o aluno; em 0 cada uma tem valor próprio"
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
        default=360, ge=1, description="W_a — carga horária máxima por período"
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
    observation_periods: int = Field(
        default=10,
        ge=1,
        le=40,
        description=(
            "quantos períodos são medidos, depois da pré-população. São os que as "
            "tabelas e os gráficos mostram"
        ),
    )

    @property
    def warmup_periods(self) -> int:
        """A pré-população — **é** o prazo de jubilamento.

        Não é campo porque não é escolha: com ingresso em todo período e
        residência R, antes de `t = R` nenhuma coorte é velha o bastante para
        sair, e a população cresce uma coorte por período. Qualquer valor menor
        mediria a rampa.
        """
        return self.max_residence

    @property
    def periods(self) -> int:
        """|T|, derivado — ver `config.horizon_for_window`."""
        return horizon_for_window(
            max_residence=self.max_residence,
            observation_periods=self.observation_periods,
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
            "se o orçamento carrega entre períodos (eq. 36) ou recomeça em C_min"
        ),
    )
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
    # f_gamma — eq. (34): γ = round(nota/10 · k · preço). Este e o `min_credits`
    # acima são do leilão por créditos e não têm efeito na linha de base por
    # CR, que não tem orçamento nem preço pago.
    return_multiplier: float = Field(
        default=2.0,
        ge=0,
        description="k — multiplica o preço pago no retorno; 0 desliga",
    )
    exclusion_refund_rate: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="fração do preço pago que a disciplina excluída devolve",
    )


class CompareRequest(ScenarioIn):
    """Uma comparação entre os três modelos sobre o mesmo cenário.

    A **seed** do cenário não tem efeito aqui, porque as seeds são 1..`runs` e
    cada uma roda nos três braços: fixar uma só mediria aquela população, e não
    parear mediria a variação entre populações junto da variação entre modelos.

    O `return_multiplier`, ao contrário, vale — mas só onde o braço não o
    fixa. O retorno é o eixo do experimento: o braço de ablação o desliga
    impondo 0, e o braço do trabalho roda com o do cenário.
    """

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
            "Quais braços rodar. O padrão são os três do trabalho — "
            "`ranking_greedy` (ordenação por CR), `credits_ilp` (leilão "
            "igualitário, orçamento fixo em C_min) e `credits_return` "
            "(leilão acumulativo). Rodar menos braços custa proporcionalmente "
            "menos tempo e serve para calibrar cenário; os painéis que "
            "comparam os ausentes simplesmente não aparecem. Também aceita o "
            "braço de ablação `credits_greedy`."
        ),
    )


class GroupBandsOut(BaseModel):
    """Um grupo de um recorte reduzido entre as seeds, ponto a ponto.

    `values[k][i]` é `[q1, mediana, q3]` da grandeza `k` no ponto `x[i]` da
    régua, ou `null` se nenhuma seed a mediu ali. `n[i]` é quantas seeds
    mediram o grupo naquele ponto.

    As grandezas de `values` são as métricas de período, os seis estados de
    uma solicitação, as quatro frações do funil (`requested_share`,
    `granted_share`, `attended_share`, `approved_share`) e um `round_<r>` por
    rodada do cenário.
    """

    model_config = ConfigDict(from_attributes=True)

    group: str
    # O ponto da régua: o número do período, a idade do aluno ou a coorte
    # dele, conforme o `ruler` do eixo.
    x: list[int]
    n: list[int]
    values: dict[str, list[tuple[float, float, float] | None]]


class AxisBandsOut(BaseModel):
    """Os grupos de um recorte espacial sob uma régua do eixo X.

    As duas dimensões são independentes na tela, e vêm todas as combinações:
    `ruler` é `period`, `age` ou `cohort`; `axis` é `overall` (um grupo só) ou
    um dos eixos de perfil — `performance`, `availability` ou `selectivity`.
    """

    model_config = ConfigDict(from_attributes=True)

    ruler: str
    axis: str
    groups: list[GroupBandsOut]


class RunSummaryOut(BaseModel):
    """Uma simulação reduzida a um ponto por métrica — o que vira uma linha
    das tabelas. As três de período são a média ponderada pelos alunos medidos, de
    modo que a fase de drenagem não pese como um período cheio; o tempo de
    formatura é da simulação inteira."""

    model_config = ConfigDict(from_attributes=True)

    seed: int
    # Períodos efetivamente publicados; menor que |T| se a população se esvaziou
    # antes do horizonte.
    periods: int
    # Concluintes da simulação — o contexto sem o qual `time_to_graduate` não se
    # lê: quem forma menos pode exibir um tempo menor só por sobrarem os rápidos.
    graduates: int
    # Jubilados da simulação, e o total que entrou — o denominador das duas
    # frações que a tela mostra.
    dismissed: int
    population: int
    efficiency: float  # eq. (53)
    # Ocupação: a contraparte em carga do psi, que é em utilidade.
    utilization: float
    # Progresso: carga aprovada sobre a carga que conclui o curso. Acumula ao
    # longo do horizonte, e lê-se com `graduates` ao lado.
    progress: float
    # Fidelidade da mensagem: quanto da preferência sobrevive à tradução.
    # Descreve, não pontua — como a correlação.
    fidelity: float
    fairness: float  # eq. (55)
    correlation: float  # eq. (57)
    # Desperdício: a fração das vagas obtidas que foi largada antes de virar
    # aula. É a quinta métrica da comparação, e a que a disponibilidade existe
    # para produzir.
    exclusion_rate: float
    # Δψ — a dissipação: a satisfação alocada que não chegou a ser consumida.
    # Custo **privado** da exclusão, contra o ε acima, que é o social.
    dissipation: float = 0.0
    # N̄ — o CR médio. Descreve, não pontua: sobe tanto por o aluno ir melhor
    # quanto por o mecanismo roteá-lo para turma mais fácil.
    grade_average: float = 0.0
    # Os seis estados em média por aluno, reduzidos a um ponto cada.
    request_states: RequestStatesOut
    # Períodos do ingresso ao diploma, na média dos concluintes. Null quando
    # ninguém concluiu.
    time_to_graduate: float | None
    # Vagas obtidas por aluno em cada rodada (o índice r-1 é a rodada r), com
    # |R| posições. Mede a **saturação**: o que se lê é o decaimento entre as
    # rodadas, não o nível de cada uma.
    allocations_per_round: list[float | None]


class ClassPriceBandsOut(BaseModel):
    """O preço médio da turma sob um recorte da **oferta**.

    É a única família de recortes que não reparte alunos — ela reparte turmas
    —, e por isso vem à parte de `series` em vez de ser mais um `axis` dela:
    cruzar "disciplina de 2 turmas" com uma métrica por aluno não produziria
    leitura nenhuma.

    `axis` é `classes`, `hours`, `difficulty` ou
    `curriculum_period`. Os grupos têm a forma das demais faixas, com uma
    grandeza só (`mean_price`), e a chave de cada um é **o valor**, sem
    idioma: `"2"`, `"60"`, `"1.4"` — e `"elective"` no recorte por período,
    onde a optativa é grupo à parte por não ter período na grade. O rótulo em
    português é da interface.

    A régua é sempre o período: as outras duas (`age`, `cohort`) são do tempo
    do **aluno**, e uma turma não tem idade nem coorte.
    """

    model_config = ConfigDict(from_attributes=True)

    axis: str
    groups: list[GroupBandsOut]


class ArmResultOut(BaseModel):
    """Um dos modelos comparados e as suas N simulações.

    `key` é o identificador estável da série; o rótulo em português é da
    interface, não da API.
    """

    model_config = ConfigDict(from_attributes=True)

    key: str
    mechanism: Mechanism
    # O k efetivamente rodado neste braço, e não o do cenário: o braço de
    # ablação o impõe em 0 para desligar o retorno.
    return_multiplier: float
    runs: list[RunSummaryOut]
    # As séries reduzidas entre as seeds: cada régua do eixo X cruzada com o
    # agregado e com cada recorte. A série de cada simulação não sai — só os
    # quartis dela.
    series: list[AxisBandsOut]
    # Segundos médios do alocador em cada (período, rodada), entre as seeds:
    # `allocation_seconds[p][r]` é a rodada r+1 do período p+1. Sai só a média
    # do braço, e não a série de cada seed — quem a lê é um gráfico global, e
    # mandar as N séries multiplicaria a resposta sem acrescentar leitura.
    #
    # É a única série daqui que **não** é do modelo: mede quanto custa rodar o
    # mecanismo, não o que ele produz. Ver `comparison.allocation_seconds`.
    allocation_seconds: list[list[float]] = []
    # O preço médio da turma por recorte da oferta. Vazio fora do leilão —
    # sem moeda não há preço —, e aí a seção some da tela.
    class_prices: list[ClassPriceBandsOut] = []


class CompareResponse(BaseModel):
    saved_to: str | None = None
    """As amostras dos três braços, pareadas pela seed: o i-ésimo elemento de
    cada lista é a mesma população sob regras diferentes."""

    model_config = ConfigDict(from_attributes=True)

    runs: int
    arms: list[ArmResultOut]


class RequestStatesOut(BaseModel):
    """Os seis estados de solicitação, em **média por aluno**.

    Particionam o que ainda falta ao aluno — o catálogo menos o que ele já
    aprovou —, de modo que a soma é o tamanho desse denominador. A ordem dos
    campos é a do funil, do mais distante ao mais bem-sucedido.

    É média, nunca soma: a soma seria governada pela população, que sobe no
    escalonamento de ingresso e despenca na drenagem, e o gráfico mostraria o
    tamanho da universidade em vez do mecanismo.
    """

    model_config = ConfigDict(from_attributes=True)

    not_eligible: float  # pré-requisito pendente, ou optativa que a cota dispensou
    not_requested: float
    refused: float  # pediu e não foi atendido — "indeferida" na tela
    excluded: float  # obteve a vaga e largou
    failed: float
    approved: float


class MetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    students: int
    allocated: int
    allocations_per_student: float
    efficiency: float  # eq. (53)
    # Ocupação: carga horária obtida no período ÷ W_a, média dos medidos. A
    # contraparte em carga do psi, que é em utilidade.
    utilization: float
    # Progresso: carga aprovada do histórico ÷ carga mínima para concluir,
    # média dos medidos. A única métrica daqui que acumula entre períodos.
    progress: float
    # Fidelidade da mensagem: cosseno entre o lance normalizado e a utilidade.
    # Mede quanto da preferência sobrevive à tradução. Descreve, não pontua.
    fidelity: float
    fairness: float  # eq. (55)
    occupancy: float  # eq. (54)
    # As grandezas da exclusão. `null` em plena rodada: a exclusão acontece
    # depois da última, então só o recorte de fim de período tem o que contar.
    #
    # As de **contagem** acima (allocated, occupancy, utilization) ficam no
    # alocado, porque a vaga saiu do sistema tenha sido cursada ou não; as de
    # **valor** (efficiency, fairness, correlation) ficam no retido, porque o
    # aluno não consumiu a utilidade do que largou. O vão entre as duas
    # leituras é o desperdício.
    excluded: int | None
    exclusion_rate: float | None
    effective_utilization: float | None  # carga **retida** / W_a, média
    request_states: RequestStatesOut | None
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
    overall: GroupSnapshotOut
    # Agregado por coorte; só as coortes que já ingressaram.
    by_cohort: list[GroupSnapshotOut]
    # E pelos dois eixos de perfil, na ordem em que o cenário os declara. Os
    # três recortes particionam a mesma população: somar qualquer um deles
    # reproduz `overall`.
    # Null quando nenhuma disciplina estava no mercado no instante.
    prices: PriceStatsOut | None


class DisciplineSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # O nome da **turma** — é dela que são a vaga, o preço e a demanda.
    name: str
    # O clique a que a turma pertence, por onde a tela agrupa.
    discipline: str
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
    # Vagas desta disciplina obtidas e depois largadas. Com `filled`, separa a
    # vaga que virou aula da que só saiu da oferta.
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
    # Os perfis do aluno, pelo nome — o recorte que a tela individual
    # mostra no cabeçalho dele, e os eixos pelos quais o relatório agrega.
    performance: str
    availability: str
    selectivity: str
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
    # 0 = vaga garantida de ingressante, concedida fora do leilão.
    won_round: int | None
    paid: int
    # Obteve a vaga e não cursou. Com ela, `attempt` e `grade` vêm null — não
    # houve tentativa — e `returned` traz metade do preço pago.
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
    enrolled_hours: int  # carga obtida no período, antes de excluir
    # Carga que ele de fato cursou e o teto que a disponibilidade lhe deu.
    # `retained_hours <= effective_load`, e o vao para `enrolled_hours` e o que
    # ele largou.
    retained_hours: int
    effective_load: int
    requests: list[RequestRecordOut]
    graduated: bool


class StudentHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    periods: list[StudentPeriodRecordOut]


class TraceRequest(ScenarioIn):
    """O traço de **uma** simulação da comparação: o cenário mais o par
    `(braço, seed)` que a identifica.

    Aqui a seed não é ignorada como em `/compare` — ela é o que se pede. A
    comparação roda as seeds de 1 a N em cada braço e devolve um ponto por
    simulação; este par é o endereço de uma delas, e a simulação é refeita em
    vez de guardada: ela é determinística, então refazê-la custa tempo e não
    fidelidade. O retorno de créditos e o resolvedor continuam vindo do braço.
    """

    arm: str = Field(
        description="chave do modelo, como em `/compare` — ex.: `credits_return`"
    )
    seed: int = Field(
        default=1,
        ge=1,
        description="qual simulação daquele braço — a mesma seed que o resumo traz",
    )


class TracePeriodOut(BaseModel):
    """O contexto de mercado de um período: a oferta disciplina a disciplina.

    É o que a vista por disciplina lê no cabeçalho de cada período — vagas,
    preenchidas, solicitantes, preço e aprovações. As métricas de aluno não
    entram: elas são da comparação, e aqui o que se olha é um caso.
    """

    model_config = ConfigDict(from_attributes=True)

    period: int
    disciplines: list[DisciplineSnapshotOut]


class TraceResponse(BaseModel):
    """Uma simulação inteira, aluno a aluno — a tela de depuração do projeto.

    É a parte pesada do resultado (uns 10 MB no preset Computação, contra 100 kB
    do resumo da comparação), e é por isso que ela não vem junto de `/compare`
    nem é guardada no navegador: quem quiser o caso individual o pede, e só
    daquela simulação.
    """

    model_config = ConfigDict(from_attributes=True)

    arm: str
    seed: int
    # A oferta de cada período, para a vista por disciplina.
    periods: list[TracePeriodOut]
    students: list[StudentSummaryOut]
    # Período a período, o que cada aluno pediu e o que recebeu.
    histories: list[StudentHistoryOut]
    # As disciplinas na ordem da grade, e o período de cada uma — induzido dos
    # pré-requisitos, não configurado.
    disciplines: list[str]
    classes: dict[str, str]
    curriculum_periods: dict[str, int]


class PlaygroundClassIn(BaseModel):
    name: str
    seats: int = Field(ge=0)
    hours: int = Field(gt=0)
    # A disciplina da turma — o clique da eq. (5). Ausente, a turma é a
    # própria disciplina.
    discipline: str | None = None


class PlaygroundStudentIn(BaseModel):
    id: str
    credits: int = Field(default=0, ge=0)
    cr: float = 0
    max_hours: int = Field(gt=0)
    utilities: dict[str, float]
    eligible: list[str]
    # Horas já realizadas; ausente, o aluno leva tudo o que obteve.
    availability: int | None = Field(default=None, ge=0)
    # O mesmo limite do perfil do cenário.
    selectivity: float = Field(default=0.0, ge=0)


class PlaygroundRequest(BaseModel):
    mechanism: Mechanism
    rounds: int = Field(ge=1, le=10)
    seed: int = 0
    mode_grade: float = Field(default=8.0, gt=0, lt=10)
    zero_rate: float = Field(default=0.005, gt=0, lt=1)
    max_rate: float = Field(default=0.008, gt=0, lt=1)
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
    name: str  # a turma cursada
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
