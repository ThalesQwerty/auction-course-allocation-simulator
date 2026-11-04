"""Schemas Pydantic para a API — o corpo da requisição já É o cenário completo
(sem persistência): a interface monta tudo no navegador e manda de uma vez.

São três entradas: `/run` recebe um leilão isolado (agentes, bens e lances
explícitos), `/compare` recebe o cenário de uma comparação — a universidade e a
população, de que alunos, utilidades e notas saem pela seed — e `/trace` recebe
o mesmo cenário mais o par `(braço, seed)` de uma das observações que ela rodou.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..auction import AuctionResult
from ..comparison import ARMS, MAX_RUNS
from ..config import (
    DEFAULT_AVAILABILITY,
    DEFAULT_PERFORMANCE,
    CreditMemory,
    CreditReturnPolicy,
    Mechanism,
    Profile,
    Resolver,
    horizon_for_lifecycle,
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
    difficulty: float = Field(
        default=1.0,
        gt=0,
        description=(
            "a dificuldade, em quantas tentativas a disciplina custa para render "
            "o que uma de "
            "dificuldade 1 rende de primeira"
        ),
    )
    attractiveness: float = Field(
        default=0.0,
        description=(
            "A_x — atratividade, a média do expoente da log-normal da utilidade: 0 é "
            "a disciplina média, negativo gravita abaixo dela e positivo acima, e em "
            "múltiplos da média o fator é e^A. É a parte do gosto comum a toda a "
            "população, enquanto `utility_sigma` é a privada de cada aluno — mesma "
            "unidade, e a razão entre as duas é a correlação de preferência entre "
            "alunos. Ordena dentro de uma mesma altura da grade, não entre alturas."
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


class ProfileIn(BaseModel):
    """Um grupo da população num dos dois eixos de perfil.

    A Beta entra por **média e concentração**, que é como se lê uma população:
    média maior é um grupo que reprova menos (desempenho) ou que exclui menos
    (disponibilidade); concentração maior é um grupo mais homogêneo em torno
    dela. `equations.beta_shape` converte no par de formas.

    O nome é rótulo de relatório e precisa ser único dentro do seu eixo.
    """

    name: str = Field(min_length=1, max_length=40)
    mean: float = Field(gt=0, lt=1, description="média da Beta, em (0, 1)")
    concentration: float = Field(gt=0, description="concentração em torno da média")

    @classmethod
    def of(cls, profile: Profile) -> "ProfileIn":
        return cls(
            name=profile.name, mean=profile.mean, concentration=profile.concentration
        )

    def to_profile(self) -> Profile:
        return Profile(name=self.name, mean=self.mean, concentration=self.concentration)


class ScenarioIn(BaseModel):
    """O cenário em si (Seção 7.2) — tudo que descreve a universidade e a
    população, sem dizer *como* ele será executado.

    Os dois modos partem daqui e acrescentam só o que lhes é próprio: uma
    observação única acrescenta a seed, e a comparação acrescenta quantas
    observações fazer. É o que garante que os dois lados de uma comparação rodem
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
    # Os dois eixos de perfil. Cada um é uma lista de grupos, e a repartição
    # entre as combinações é **igualitária**: com 3 em cada eixo são 9 pares e
    # ~11% da coorte em cada um. Não há porcentagem a enviar — o que define as
    # fatias é quantos perfis existem.
    performance_profiles: list[ProfileIn] = Field(
        default_factory=lambda: [ProfileIn.of(x) for x in DEFAULT_PERFORMANCE],
        min_length=1,
        description="perfis de desempenho: governam a Beta da aptidão",
    )
    availability_profiles: list[ProfileIn] = Field(
        default_factory=lambda: [ProfileIn.of(x) for x in DEFAULT_AVAILABILITY],
        min_length=1,
        description=(
            "perfis de disponibilidade: governam a Beta da fração de W_a que o "
            "aluno de fato cursa, sorteada a cada período"
        ),
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
            "acrescenta no denominador do expoente. 1 recupera a dificuldade "
            "dividida pela tentativa"
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
    entry_periods: int = Field(
        default=8,
        ge=1,
        le=40,
        description=(
            "em quantos períodos entra coorte nova, contados do primeiro. Depois "
            "do último ingresso vem a fase de drenagem, em que a população só diminui."
        ),
    )
    max_residence: int = Field(
        default=12,
        ge=1,
        le=40,
        description=(
            "períodos que o aluno tem para concluir, contados do ingresso. Quem chega "
            "ao fim do último sem fechar a grade é jubilado e sai da simulação."
        ),
    )

    @property
    def periods(self) -> int:
        """|T|, derivado — ver `config.horizon_for_lifecycle`.

        Não é campo porque não é escolha: a última coorte sai ao fim da
        residência dela e depois disso não há mais ninguém a simular. Deixá-lo
        configurável permitiria um horizonte que corta coortes pela metade ou
        que roda períodos vazios no fim.
        """
        return horizon_for_lifecycle(
            entry_periods=self.entry_periods, max_residence=self.max_residence
        )
    students_per_period: int = Field(
        default=1,
        ge=1,
        description=(
            "alunos que ingressam em cada período com ingresso; a população é isto "
            "vezes a quantidade desses períodos. "
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
            "São N × |arms| simulações no total, e a seed pareia os braços."
        ),
    )
    arms: list[str] = Field(
        default_factory=lambda: [arm.key for arm in ARMS],
        min_length=1,
        description=(
            "Quais braços rodar. O padrão são os dois do trabalho — "
            "`ranking_greedy` e `credits_return`. Rodar um só custa metade do "
            "tempo e serve para calibrar cenário; os painéis que comparam os "
            "dois lados simplesmente não aparecem. Também aceita os braços de "
            "ablação, `credits_greedy` e `credits_ilp`."
        ),
    )


class GenomeLevelsIn(BaseModel):
    """Os valores fixados da 1ª geração, um conjunto por gene.

    O **produto** deles é o tamanho da população inicial, e precisa bater com
    `students_per_period`: sobrar genótipo faria parte da grade não rodar, e
    faltar faria alguns pesarem o dobro na seleção. Os padrões dão
    5 · 3 · 3 · 4 = 180.

    Os níveis de `alpha_u` são o fundo de [0, 1] de propósito. Como as
    utilidades elegíveis somam 1, no máximo `⌊1/α_u⌋` disciplinas passam do
    corte, e a maior participação de uma linha de n disciplinas vale em média
    `H_n/n` — cerca de 0,31 com n = 9. Níveis redondos como ⅔ e 1 não seriam
    estratégias, seriam desligamentos.
    """

    beta_u: list[float] = Field(default=[-1.0, 0.0, 1.0, 2.0, 3.0], min_length=1)
    beta_v: list[float] = Field(default=[-1.0, 0.0, 1.0], min_length=1)
    beta_n: list[float] = Field(default=[-1.0, 0.0, 1.0], min_length=1)
    alpha_u: list[float] = Field(default=[0.0, 0.05, 0.11, 0.22], min_length=1)


class EvolveRequest(ScenarioIn):
    """Uma rodada do algoritmo genético sobre o cenário.

    Custa `observations × gerações` simulações completas, então os dois tetos
    são o que separa um teste de minutos de um de horas.
    """

    # A seed do cenário vale aqui, ao contrário de `/compare`: ela fixa a
    # população e, por um fluxo próprio, o sorteio da evolução. As seeds das
    # observações continuam sendo 1..N, de modo que o que muda entre gerações
    # é o genoma e nada mais.
    seed: int = 0
    levels: GenomeLevelsIn = Field(default_factory=GenomeLevelsIn)
    observations: int = Field(
        default=5,
        ge=1,
        le=50,
        description=(
            "N — observações da simulação por geração. O erro padrão da aptidão "
            "de um genótipo é 1,36/√N: 0,61 com 5 e 0,30 com 20, contra um "
            "efeito extremo-a-extremo de 0,7. Com N baixo o torneio vira "
            "quase sorteio."
        ),
    )
    min_generations: int = Field(default=5, ge=1, le=200)
    max_generations: int = Field(default=30, ge=1, le=200)
    window: int = Field(
        default=5, ge=2, le=50, description="a janela do critério de parada"
    )
    epsilon: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "o limiar de deriva. Vazio desliga o gatilho e a rodada vai até o "
            "teto — é o que o controle negativo usa, porque é ele quem produz "
            "o ε."
        ),
    )
    tournament: int = Field(default=2, ge=2, le=20)
    elites: int = Field(default=10, ge=0, le=200)
    step: float = Field(
        default=0.3,
        ge=0.0,
        le=5.0,
        description="o passo da mutação como fração do espaçamento de cada gene",
    )
    neutral: bool = Field(
        default=False,
        description=(
            "controle negativo: o genoma é selecionado e mutado mas não chega "
            "à simulação, de modo que o que a população andar é deriva"
        ),
    )


class CohortGenerationOut(BaseModel):
    entry_period: int
    # A média de cada gene, na ordem beta_u, beta_v, beta_n, alpha_u.
    mean: list[float]
    best_fitness: float
    mean_fitness: float


class GenerationOut(BaseModel):
    generation: int
    cohorts: list[CohortGenerationOut]
    # `null` enquanto a janela não fecha — JSON não tem infinito.
    drift: float | None


class EvolveResponse(BaseModel):
    # Onde a observação foi gravada, ou `null` se o disco recusou. Quem pediu a
    # simulação quer o resultado: falhar a requisição porque o registro não
    # coube seria o pior dos dois mundos.
    saved_to: str | None = None
    generations: list[GenerationOut]
    stopped_by: str
    neutral: bool
    # O espalhamento de cada gene na 1ª geração: a escala fixa da deriva, e o
    # que torna o ε de uma rodada comparável ao de outra.
    scales: list[float]


class PeriodSeriesOut(BaseModel):
    """As métricas de período de uma observação, sem reduzir — o que o recorte
    por período da tela desenha.

    Listas **paralelas** e só com os períodos medidos: `period[i]` é o número do
    período a que `efficiency[i]` se refere. O primeiro período não aparece (nele
    todo mundo acabou de ingressar), e por isso o número vem explícito em vez de
    sair do índice. `students` é o peso do ponto na média ponderada, e cai à
    vista na drenagem.

    Sem tempo de formatura: é da observação inteira, e a versão por período seria
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
    exclusion_rate: list[float]
    # A série da seção "Solicitações de disciplinas": seis linhas não
    # empilhadas, em média por aluno, uma posição por período medido.
    request_states: list[RequestStatesOut]
    # A saturação do período, rodada a rodada: a posição [i][r] é o que foi
    # ganho por aluno na rodada r+1 do período `period[i]`. Uma linha por
    # período medido, sempre com |R| posições.
    allocations_per_round: list[list[float | None]]


class CohortSeriesOut(BaseModel):
    """O mesmo resumo da observação, uma linha por coorte — o terceiro eixo da
    tela.

    A coorte é o período de ingresso (t_a), e o aluno fica nela do ingresso ao
    diploma. A redução é a mesma do agregado; o que muda é sobre quem ela corre.

    **As coortes não são intercambiáveis**: a primeira encontra uma
    universidade quase vazia e a última a encontra cheia, de modo que a
    inclinação ao longo do eixo mistura mecanismo e mercado. O que se lê com
    segurança é a comparação entre braços num mesmo ponto.

    Aqui o tempo de formatura entra — cada aluno pertence a uma coorte só —, e
    vem com os concluintes, o denominador sem o qual ele não se lê: a contagem
    e a fração dela sobre quantos entraram naquela coorte.
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
    exclusion_rate: list[float]
    request_states: list[RequestStatesOut]
    time_to_graduate: list[float | None]
    allocations_per_round: list[list[float | None]]


class RunSummaryOut(BaseModel):
    """Uma observação reduzida a um ponto por métrica — o que vira um valor no
    boxplot. As três de período são a média ponderada pelos alunos medidos, de
    modo que a fase de drenagem não pese como um período cheio; o tempo de
    formatura é da observação inteira."""

    model_config = ConfigDict(from_attributes=True)

    seed: int
    # Períodos efetivamente publicados; menor que |T| se a população se esvaziou
    # antes do horizonte.
    periods: int
    # Concluintes da observação — o contexto sem o qual `time_to_graduate` não se
    # lê: quem forma menos pode exibir um tempo menor só por sobrarem os rápidos.
    graduates: int
    # Jubilados da observação, e o total que entrou — o denominador das duas
    # frações que a tela mostra.
    dismissed: int
    population: int
    efficiency: float  # eq. (53)
    # Aproveitamento: a contraparte em carga do psi, que é em utilidade.
    utilization: float
    # Fidelidade da mensagem: quanto da preferência sobrevive à tradução.
    # Descreve, não pontua — como a correlação.
    fidelity: float
    fairness: float  # eq. (55)
    correlation: float  # eq. (57)
    # Desperdício: a fração das vagas obtidas que foi largada antes de virar
    # aula. É a quinta métrica da comparação, e a que a disponibilidade existe
    # para produzir.
    exclusion_rate: float
    # Os seis estados em média por aluno, reduzidos a um ponto cada. A série
    # sem reduzir está em `by_period` e `by_cohort`.
    request_states: RequestStatesOut
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
    # O mesmo resumo por coorte: a mesma redução, corrida sobre outro recorte.
    by_cohort: CohortSeriesOut


class ArmResultOut(BaseModel):
    """Um dos modelos comparados e as suas N observações.

    `key` é o identificador estável da série; o rótulo em português é da
    interface, não da API.
    """

    model_config = ConfigDict(from_attributes=True)

    key: str
    mechanism: Mechanism
    credit_return: CreditReturnPolicy
    runs: list[RunSummaryOut]


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
    refused: float
    excluded: float  # obteve a vaga e largou
    failed: float
    approved: float


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
    # Os dois perfis do aluno, pelo nome — o recorte que a tela individual
    # mostra no cabeçalho dele.
    performance: str
    availability: str
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
    """O traço de **uma** observação da comparação: o cenário mais o par
    `(braço, seed)` que a identifica.

    Aqui a seed não é ignorada como em `/compare` — ela é o que se pede. A
    comparação roda as seeds de 1 a N em cada braço e devolve um ponto por
    observação; este par é o endereço de uma delas, e a simulação é refeita em
    vez de guardada: ela é determinística, então refazê-la custa tempo e não
    fidelidade. O retorno de créditos e o resolvedor continuam vindo do braço.
    """

    arm: str = Field(
        description="chave do modelo, como em `/compare` — ex.: `credits_return`"
    )
    seed: int = Field(
        default=1,
        ge=1,
        description="qual observação daquele braço — a mesma seed que o resumo traz",
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
    """Uma observação inteira, aluno a aluno — a tela de depuração do projeto.

    É a parte pesada do resultado (uns 10 MB no preset Computação, contra 100 kB
    do resumo da comparação), e é por isso que ela não vem junto de `/compare`
    nem é guardada no navegador: quem quiser o caso individual o pede, e só
    daquela observação.
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
    curriculum_periods: dict[str, int]


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
