"""Comparação entre os modelos de alocação (Seção 7.3).

O anteprojeto impõe duas condições metodológicas à comparação, e este módulo
existe para fazer as duas valerem de uma vez:

1. **Mesma inicialização dos dois lados.** "Sempre que os mecanismos forem
   comparados entre si, ambos serão inicializados com a mesma configuração de
   parâmetros iniciais, tais como alunos, cursos, períodos, disciplinas,
   utilidades, notas, entre outros." Como tudo isso é derivado da seed, basta
   rodar o mesmo cenário com a mesma seed nos dois mecanismos — é literalmente
   a mesma população, a mesma matriz de utilidades e a mesma matriz de notas
   encontrando regras de alocação diferentes.
2. **Múltiplas configurações de entrada.** "Serão testadas múltiplas
   configurações de entrada diferentes para cada comparação, e o resultado
   médio das simulações será avaliado." As seeds de 1 a N são essas
   configurações: N populações diferentes, cada uma vista pelos dois
   mecanismos.

Juntas, as duas isolam o nexo causal no mecanismo. Uma execução só não diria
nada — a diferença poderia ser daquela população; e N execuções sem parear as
seeds mediriam a variação entre populações junto da variação entre mecanismos.

**Os braços são um caminho de quatro passos** (`ARMS`), e cada seta muda
**uma** coisa só — é o que torna o vão atribuível. Comparar a linha de base
direto com o leilão mediria mensagem e resolução somadas, sem dizer qual
pesou.

    CR  ──mensagem──▶  Bidding points  ──resolução──▶  Leilão sem retorno
                                                   ──retorno──▶  Leilão com retorno

1. **A mensagem.** O CR dá um número por *aluno*; o lance dá um número por
   *par* (aluno, disciplina). É a intensidade entrando no que o mecanismo
   recebe. Os dois lados resolvem ordinalmente, então o passo isola a moeda.
   Não é o mesmo algoritmo dos dois lados (`serial_dictatorship` contra
   `greedy_allocation`), e não poderia ser: um número por aluno não dá para
   ordenar pares. "Ordinal" descreve a **propriedade** — nenhum dos dois
   troca magnitudes —, não a implementação.
2. **A resolução.** Ordinal usa só a *ordem* dos lances: qualquer
   transformação monótona do vetor dá a mesma alocação. Cardinal (PLI) usa as
   *magnitudes*, e derruba um lance alto para acomodar dois médios, o que a
   varredura nunca faz. Os dois só divergem onde a carga horária aperta — sem
   ela o problema se separa por disciplina e a varredura é ótima —, então o
   passo só tem conteúdo em cenário com conjunto elegível maior que W_a.
3. **O retorno.** `f_γ` proporcional (eq. 34): quem aprova recupera a fatia
   do preço correspondente à nota, de modo que ir bem compra poder de compra
   no período seguinte. É a única fonte de mérito do leilão — a ordenação por
   CR faz isso por construção, o histórico *é* o critério, e o leilão sem
   retorno não faz de jeito nenhum.

**Por que o retorno leva ablação e a sobra não.** A sobra é a eq. (36), dada
pelo anteprojeto; a política de retorno a Seção 7.3.2 deixa explicitamente em
aberto, como eixo de experimentação. Escolher `ratio` como canônico é decisão
de quem escreve, e o passo 3 é onde ela se paga.

Por isso a política de retorno e o resolvedor **não são parâmetros do cenário
aqui**: são eixos do experimento, e o que vier na configuração é ignorado,
como a seed. Cada braço impõe o seu.

**Uma execução vira um número por métrica**, que é o ponto do boxplot. Para as
três métricas de período a redução é a média **ponderada pelos alunos medidos**:
a simulação termina numa fase de drenagem, em que a população só diminui, e uma
média simples daria a um período final de vinte alunos o mesmo peso de um
período cheio de trezentos. Ponderar pela população corrige isso sem recortar o
horizonte à mão.

O peso são os alunos **medidos** (`metrics.students`), não os ativos: o calouro
conta como gente e não como dado (ver `simulation.GroupSnapshot`), e o primeiro
período, em que todo mundo acabou de ingressar, simplesmente não entra na média.

**As quatro métricas.** Satisfação (psi-barra), equidade (phi) e correlação
(lambda) são de período e passam pela média ponderada. O **tempo de formatura**
não é: é propriedade da execução inteira, a média de quantos períodos cada
concluinte levou do ingresso ao diploma.

Ficaram de fora, e por motivos diferentes. Nada de **crédito**: orçamento, preço
e retorno não existem do lado da linha de base, e comparar um mecanismo com o
vazio não é comparação. A **ocupação** (theta) saiu porque, com o calouro fora do
recorte, ela deixou de se ler como "o quanto a universidade encheu" — as vagas
garantidas continuam ocupadas e não entram mais no numerador; quem quer essa
leitura a tem nos gráficos por disciplina. E a **semestralização** deu lugar ao
tempo de formatura, que mede a mesma coisa — progressão na grade — num número
que se lê direto, em períodos.

**O tempo de formatura tem viés de seleção, e por isso não anda sozinho.** A
média só existe sobre quem concluiu: um mecanismo que forma menos gente pode
exibir um tempo *menor* só porque sobraram os rápidos. Daí `graduates` vir junto
no resumo — a média não se lê sem ele.

**A saturação** sai de `allocations_per_round`: as vagas obtidas por aluno em
cada rodada, uma média por rodada em vez de uma só para o período. O que se lê
é o **decaimento** entre elas. Um mecanismo que atende mais demanda cedo começa
alto e cai rápido; um que leva a disputa adiante distribui as vagas pelas
rodadas. É o perfil, não o nível, que responde "satura mais rápido?" — e o
nível, somado, é a mesma `allocations_per_student` do período.

Conta-se o que foi ganho **naquela rodada**, não o acumulado: `RoundReport` traz
o `won_now`, não o `won`. E, como o calouro está fora do recorte, a matrícula
garantida não infla a primeira rodada — o número é só o que o mecanismo alocou.
"""
from __future__ import annotations

import dataclasses
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np

from .behavior import draw_utilities
from .equations import (
    grade_for_attempt,
    grade_histogram,
    utility_histogram,
    weighted_mean,
)
from .equations import time_to_graduate as mean_span
from .grading import draw_aptitudes
from .config import (
    CreditMemory,
    CreditReturnPolicy,
    Mechanism,
    Resolver,
    SimulationConfig,
)
from .metrics import Metrics
from .population import generate_students
from .simulation import SimulationResult, run_simulation

# Teto de execuções por braço. Não é limitação técnica: é que o boxplot para de
# ganhar informação muito antes disso, e cada execução a mais custa uma
# simulação inteira em cada braço.
MAX_RUNS = 100

@dataclass(frozen=True)
class Arm:
    """Um dos modelos comparados.

    Um modelo é a combinação de quatro escolhas: a **moeda** (ordenação por CR
    ou lance em créditos), o **resolvedor** (varredura gulosa ou PLI global),
    a **memória do orçamento** (se a sobra atravessa o período) e a **política
    de retorno**.

    `key` é o identificador estável que a interface usa para rotular a série —
    o rótulo em si é dela, não daqui.
    """

    key: str
    mechanism: Mechanism
    credit_return: CreditReturnPolicy
    resolver: Resolver = "ilp"
    credit_memory: CreditMemory = "carry"


# Os braços na ordem do caminho — é também a ordem do eixo, da legenda e das
# cores, e nela a correlação (eq. 57) se lê de uma vez: do mecanismo em que o
# CR é o próprio critério ao que o ignora por completo.
#
# **Só entra aqui o que sai nos resultados**: cada braço é uma caixa do
# boxplot e uma linha das tabelas, e nada roda para não ser mostrado. Duas
# células que já foram braços saíram por não serem passos do caminho — o CR
# resolvido por PLI (que tem defeito declarado: como todo pedido do aluno tem
# o mesmo peso N_a, a PLI é indiferente sobre qual cortar, e o aluno não tem
# voz sobre o que perde) e o leilão sem sobra. As duas seguem alcançáveis por
# `SimulationConfig` — `resolver="ilp"` com `mechanism="ranking"`, e
# `credit_memory="none"` — se um dia forem precisas para um apêndice.
ARMS: tuple[Arm, ...] = (
    # `credits_greedy` é o *bidding points* clássico — orçamento de pontos,
    # lances por disciplina, disciplina fechando no menor lance atendido
    # (Sönmez & Ünver 2010, sobre Michigan e Yale SOM). Não confundir com o
    # **Course Match** de Wharton, que substituiu o bidding points de lá:
    # aquele é cardinal e resolve por MIP, mas é outro mecanismo —
    # preferências sobre *cestas*, orçamentos aproximadamente iguais e preços
    # de equilíbrio, não lance pago a segundo preço. É trabalho relacionado,
    # não célula deste desenho.
    Arm("ranking_greedy", "ranking", "none", resolver="greedy"),
    Arm("credits_greedy", "credits", "none", resolver="greedy"),
    Arm("credits_ilp", "credits", "none", resolver="ilp"),
    Arm("credits_return", "credits", "ratio"),
)

# Os braços por chave — como a interface se refere a um deles ao pedir o traço
# de uma execução.
ARM_BY_KEY: dict[str, Arm] = {arm.key: arm for arm in ARMS}


@dataclass(frozen=True)
class PeriodSeries:
    """As métricas de período de uma execução, sem reduzir.

    É o mesmo material de que `summarize` tira a média ponderada — a diferença
    é que aqui ele não vira um número. A média esconde que o horizonte tem três
    trechos: o **aquecimento**, com a universidade enchendo; o **estado
    estacionário**; e a **drenagem**, depois do último ingresso, em que a
    população só diminui. De um vão entre mecanismos a pergunta seguinte é em
    qual dos três ele mora — um leilão que só ganha do CR na drenagem disse
    algo sobre a drenagem, não sobre o mecanismo.

    As listas são **paralelas** e trazem só os períodos **medidos**: `period[i]`
    é o número do período a que `efficiency[i]` se refere, e posição nenhuma é
    nula. O primeiro período não aparece — nele todo mundo acabou de ingressar
    e não há o que medir (ver `summarize`) —, e por isso o número do período vem
    explícito em vez de sair do índice.

    `students` é o peso daquele ponto na redução. Ele cai à vista na drenagem, e
    é o que torna a ponderação verificável em vez de confiável: quem lê o
    gráfico vê o período final de vinte alunos que a média ponderada se recusou
    a tratar como um período cheio.

    A saturação também está aqui, e com uma dimensão a mais: ela já é uma série
    por rodada, e por período vira uma matriz. Lê-se uma rodada de cada vez —
    como a tela faz, um gráfico por rodada —, e aí cada uma é outra série sobre
    o mesmo eixo.

    O tempo de formatura não está aqui, e não por recorte de escopo: é
    propriedade da execução inteira. A versão por período — quanto levou quem
    concluiu em t — seria outra grandeza, com viés de sobrevivência, porque
    quem conclui cedo é rápido por construção.
    """

    period: list[int]
    students: list[int]
    efficiency: list[float]
    utilization: list[float]
    fidelity: list[float]
    fairness: list[float]
    correlation: list[float]
    # A saturação do período, rodada a rodada: `allocations_per_round[i][r]` é o
    # que foi ganho por aluno na rodada r+1 do período `period[i]`. Uma linha
    # por período medido, sempre com |R| posições — `None` onde aquele período
    # não publicou a rodada, ou não teve o que medir nela.
    #
    # O peso desta série é o **mesmo** `students` acima, e isso não é
    # coincidência: o recorte de um período é o mesmo em todas as rodadas — a
    # rodada muda o que foi alocado, não quem é medido.
    allocations_per_round: list[list[float | None]]


@dataclass(frozen=True)
class CohortSeries:
    """O mesmo resumo da execução, uma linha por geração.

    A geração é o período de ingresso (t_a): a geração 3 é quem entrou no
    período 3, e o aluno fica nela do ingresso ao diploma — o que torna esta
    leitura mais estável que a idade acadêmica. O recorte **particiona** a
    população, então somá-lo reproduz o agregado.

    Cada ponto é a mesma média ponderada de `summarize`, restrita aos instantes
    daquela geração: o eixo troca de significado, a redução não.

    **As gerações não são intercambiáveis, e é o que torna este eixo
    traiçoeiro.** A geração 1 encontra uma universidade quase vazia e a última
    encontra a cheia, de modo que a inclinação ao longo do eixo mistura o
    mecanismo com o mercado que cada uma pegou. O que se lê aqui com segurança
    é a comparação **vertical** — os braços num mesmo ponto do eixo, que é a
    mesma geração da mesma população sob regras diferentes.

    Aqui o **tempo de formatura entra**, e por um motivo que o recorte por
    período não tem: cada aluno pertence a exatamente uma geração, e o tempo do
    ingresso ao diploma é propriedade dele. Vem com os concluintes ao lado —
    o denominador sem o qual ele não se lê —, e que nas últimas gerações são
    poucos ou nenhum, porque o horizonte acabou antes de elas terem tempo.
    """

    # O t_a de cada geração, em ordem. Só as que tiveram algum instante medido:
    # quem entrou no último período não chegou a ser medido, e uma linha vazia
    # ali não seria dado.
    cohort: list[int]
    graduates: list[int]
    # A fração da geração que concluiu: os concluintes sobre quantos entraram
    # naquele período. É ela que se desenha, e não a contagem: o absoluto
    # depende do tamanho do ingresso, a fração é comparável entre gerações.
    graduation_rate: list[float]
    efficiency: list[float]
    utilization: list[float]
    fidelity: list[float]
    fairness: list[float]
    correlation: list[float]
    # `None` na geração em que ninguém concluiu — zero ali se leria como
    # "formou na hora".
    time_to_graduate: list[float | None]
    # A saturação da geração, rodada a rodada: a posição [i][r] é a rodada r+1
    # da geração `cohort[i]`, na média ponderada sobre os períodos dela.
    allocations_per_round: list[list[float | None]]


@dataclass(frozen=True)
class RunSummary:
    """Uma execução reduzida a um ponto por métrica.

    `periods` é quantos períodos a simulação de fato publicou — pode ser menor
    que |T| se a população se esvaziou antes do horizonte —, e serve para
    conferir que todos os braços viveram o mesmo intervalo. `graduates` é o
    contexto sem o qual `time_to_graduate` não se lê.
    """

    seed: int
    periods: int
    graduates: int  # quantos concluíram o curso — eq. (40)
    efficiency: float  # psi-barra — eq. (53)
    # Aproveitamento: a contraparte em carga do psi, que é em utilidade. As
    # duas se separam onde está a patologia que interessa — quem concentra o
    # lance, ganha a disciplina que amava e deixa o resto de W_a ocioso pontua
    # psi alto e aproveitamento baixo.
    utilization: float
    # Fidelidade da mensagem: quanto da preferência sobrevive à tradução para
    # o que o mecanismo de fato recebe. **Descreve, não pontua** — como a
    # correlação, ela não ganha "seeds a favor": dizer qual lado é melhor
    # exigiria escolher entre expressar intensidade e ser simples de usar.
    fidelity: float
    fairness: float  # phi de Jain — eq. (55)
    correlation: float  # lambda — eq. (57)
    # Períodos do ingresso ao diploma, na média dos concluintes. `None` quando
    # ninguém concluiu: a média não existe, e 0 ali se leria como "formou na
    # hora", que é o contrário do que aconteceu.
    time_to_graduate: float | None
    # Vagas obtidas por aluno **em cada rodada**, na ordem delas: o índice r-1 é
    # a rodada r. Tem |R| posições, iguais em todos os braços porque o cenário é
    # o mesmo. `None` numa posição significa que nenhum período teve o que medir
    # naquela rodada.
    allocations_per_round: list[float | None]
    # As mesmas métricas de período, período a período — o que a média ponderada
    # resume. É o recorte por período da tela; a redução continua sendo a dos
    # campos acima, e as duas leituras saem do mesmo material.
    by_period: PeriodSeries
    # O mesmo resumo por geração — o terceiro eixo da tela. Aqui a redução é a
    # mesma; o que muda é sobre quem ela corre.
    by_cohort: CohortSeries


@dataclass(frozen=True)
class ArmResult:
    """As N execuções de um braço, na ordem das seeds."""

    key: str
    mechanism: Mechanism
    credit_return: CreditReturnPolicy
    runs: list[RunSummary]


@dataclass(frozen=True)
class ComparisonResult:
    """As N execuções de cada braço, pareadas pela seed.

    Todas as listas têm o mesmo tamanho e a mesma ordem de seeds: o i-ésimo
    elemento de cada uma é a *mesma* população sob regras diferentes. Quem lê
    pode tanto tratar cada lista como uma amostra (é o que o boxplot faz) quanto
    comparar par a par — e a comparação par a par é a que responde "o retorno
    mudou alguma coisa?", porque ali a população é literalmente a mesma.
    """

    runs: int
    arms: list[ArmResult]
    # As duas distribuições de entrada do cenário, para a tela mostrar de onde
    # vieram os números. Não variam entre braços nem entre seeds — são do
    # cenário, não da execução.
    utility_distribution: list[float] = field(default_factory=list)
    grade_distribution: list[float] = field(default_factory=list)


def time_to_graduate(result: SimulationResult) -> float | None:
    """Períodos do ingresso ao diploma — ver `equations.time_to_graduate`."""
    return mean_span(
        s.graduated_at - s.entry_period + 1
        for s in result.students
        if s.graduated_at is not None
    )


def allocations_per_round(result: SimulationResult) -> list[float | None]:
    """Vagas obtidas por aluno em cada rodada, na ordem delas.

    Uma posição por rodada do cenário, e a mesma média ponderada pelos alunos
    medidos que as métricas de período usam. O valor é o que foi ganho *naquela*
    rodada — `RoundReport` traz o `won_now` —, de modo que a série decai: a
    primeira rodada pega o que estava livre, as seguintes o que sobrou.
    """
    rounds = max((len(period.rounds) for period in result.periods), default=0)
    series: list[float | None] = []
    for index in range(rounds):
        series.append(
            weighted_mean(
                [
                    (metrics.allocations_per_student, metrics.students)
                    for period in result.periods
                    if index < len(period.rounds)
                    for metrics in [period.rounds[index].overall.metrics]
                    if metrics is not None and metrics.students > 0
                ]
            )
        )
    return series


def cohort_series(result: SimulationResult) -> CohortSeries:
    """Reduz a execução geração a geração.

    É a mesma média ponderada de `summarize`, corrida sobre `by_cohort` em vez
    de `overall`. O recorte particiona a população, então nenhum aluno-período
    é contado duas vezes nem fica de fora — e somar as gerações de um período
    reproduz o agregado dele.

    A filtragem é a mesma do agregado, pelo mesmo motivo: instante sem métrica
    não entra, e uma geração não tem métrica no período em que ingressou,
    porque ali ela é toda calouro e o calouro conta como gente, não como dado
    (ver `simulation.GroupSnapshot`).

    O tempo de formatura e os concluintes não saem dos instantes, e sim de
    varrer os alunos: cada um pertence a uma geração só, pelo `entry_period`.
    De lá sai também o tamanho do ingresso, que é o denominador da fração —
    e que conta **todo mundo** que entrou, inclusive quem nunca chegou a ser
    medido.
    """
    rounds = max((len(period.rounds) for period in result.periods), default=0)

    instants: dict[int, list[tuple[Metrics, int]]] = defaultdict(list)
    saturation: dict[int, list[list[tuple[float, int]]]] = defaultdict(
        lambda: [[] for _ in range(rounds)]
    )

    def collect(report, into) -> None:
        for snapshot in report.by_cohort:
            metrics = snapshot.metrics
            if snapshot.group is None or metrics is None or metrics.students <= 0:
                continue
            into(int(snapshot.group), metrics)

    for period in result.periods:
        collect(
            period.aggregate,
            lambda cohort, metrics: instants[cohort].append((metrics, metrics.students)),
        )
        for index in range(min(rounds, len(period.rounds))):
            collect(
                period.rounds[index],
                lambda cohort, metrics, index=index: saturation[cohort][index].append(
                    (metrics.allocations_per_student, metrics.students)
                ),
            )

    cohorts = sorted(instants)
    entrants: dict[int, int] = defaultdict(int)
    graduates: dict[int, int] = defaultdict(int)
    spans: dict[int, list[int]] = defaultdict(list)
    for student in result.students:
        entrants[student.entry_period] += 1
        if student.graduated_at is None:
            continue
        graduates[student.entry_period] += 1
        spans[student.entry_period].append(
            student.graduated_at - student.entry_period + 1
        )

    def mean(cohort: int, of) -> float:
        return weighted_mean([(of(m), w) for m, w in instants[cohort]]) or 0.0

    return CohortSeries(
        cohort=cohorts,
        graduates=[graduates[cohort] for cohort in cohorts],
        graduation_rate=[
            graduates[cohort] / entrants[cohort] if entrants[cohort] else 0.0
            for cohort in cohorts
        ],
        efficiency=[mean(c, lambda m: m.efficiency) for c in cohorts],
        utilization=[mean(c, lambda m: m.utilization) for c in cohorts],
        fidelity=[mean(c, lambda m: m.fidelity) for c in cohorts],
        fairness=[mean(c, lambda m: m.fairness) for c in cohorts],
        correlation=[mean(c, lambda m: m.correlation) for c in cohorts],
        time_to_graduate=[mean_span(spans[cohort]) for cohort in cohorts],
        allocations_per_round=[
            [weighted_mean(pairs) for pairs in saturation[cohort]] for cohort in cohorts
        ],
    )


def summarize(result: SimulationResult, *, seed: int) -> RunSummary:
    """Reduz uma simulação inteira a um ponto por métrica.

    As três de período passam pela média ponderada pelos alunos medidos; o tempo
    de formatura é da execução inteira; a saturação é uma média dessas por
    rodada. O ponto não substitui o material de que saiu: `by_period` leva as
    mesmas métricas sem reduzir, e as duas leituras ficam conferíveis uma contra
    a outra.

    Períodos sem métrica não entram — nem os vazios, nem aquele em que todo
    mundo acabou de ingressar. Um zero ali seria um período em que ninguém ficou
    satisfeito, que é coisa diferente de um período que não se mede.
    """
    graduates = sum(1 for s in result.students if s.graduated_at is not None)
    measured = [
        (period, period.aggregate.overall.metrics)
        for period in result.periods
        if period.aggregate.overall.metrics is not None
        and period.aggregate.overall.metrics.students > 0
    ]
    by_period = [(metrics, metrics.students) for _, metrics in measured]
    rounds = max((len(period.rounds) for period in result.periods), default=0)

    def mean(of) -> float:
        return weighted_mean([(of(m), w) for m, w in by_period]) or 0.0

    def series(of) -> list:
        return [of(metrics) for _, metrics in measured]

    def saturation(period) -> list[float | None]:
        """A saturação de um período, com uma posição por rodada do cenário.

        Períodos que publicaram menos rodadas são completados com `None`, para
        a linha i continuar tendo o mesmo comprimento em todas: quem lê a
        coluna r está lendo a mesma rodada em todos os períodos.
        """
        row: list[float | None] = []
        for index in range(rounds):
            report = period.rounds[index] if index < len(period.rounds) else None
            metrics = report.overall.metrics if report is not None else None
            row.append(
                metrics.allocations_per_student
                if metrics is not None and metrics.students > 0
                else None
            )
        return row

    return RunSummary(
        seed=seed,
        periods=len(result.periods),
        graduates=graduates,
        efficiency=mean(lambda m: m.efficiency),
        utilization=mean(lambda m: m.utilization),
        fidelity=mean(lambda m: m.fidelity),
        fairness=mean(lambda m: m.fairness),
        correlation=mean(lambda m: m.correlation),
        time_to_graduate=time_to_graduate(result),
        allocations_per_round=allocations_per_round(result),
        by_period=PeriodSeries(
            period=[period.period for period, _ in measured],
            students=series(lambda m: m.students),
            efficiency=series(lambda m: m.efficiency),
            utilization=series(lambda m: m.utilization),
            fidelity=series(lambda m: m.fidelity),
            fairness=series(lambda m: m.fairness),
            correlation=series(lambda m: m.correlation),
            allocations_per_round=[saturation(period) for period, _ in measured],
        ),
        by_cohort=cohort_series(result),
    )


# A seed da amostra dos histogramas. É a **primeira da comparação**, e não a do
# cenário: numa comparação a seed do cenário é ignorada (ela vira o eixo da
# amostra), e usar `config.seed` faria dois cenários idênticos a menos da seed
# devolverem resultados diferentes — justamente o que a comparação promete que
# não acontece. Com 1, o histograma descreve literalmente a primeira população
# que a comparação rodou.
SAMPLE_SEED = 1


def sample_distribution(config: SimulationConfig) -> list[float]:
    """O histograma de utilidades do cenário, sorteado à parte da simulação.

    Descreve a **entrada**, não o resultado: a mesma distribuição que a
    simulação usa, numa amostra própria. Vem daqui, e não de uma execução,
    porque numa comparação há 3N matrizes, todas da mesma distribuição, sem uma
    que seja "a" certa. (Na execução única, ao contrário, o histograma sai da
    matriz que a simulação de fato usou.)
    """
    students = generate_students(config, np.random.default_rng(SAMPLE_SEED))
    rows = draw_utilities(students, config, np.random.default_rng(SAMPLE_SEED))
    return utility_histogram(rows.values())


def sample_grade_distribution(config: SimulationConfig) -> list[float]:
    """O histograma de notas de primeira tentativa, pelo mesmo motivo e do mesmo
    jeito que `sample_distribution`.

    A nota mostrada é a de **primeira tentativa, dificuldade 1 e sem ruído**:
    `a^1`, ou seja, a própria aptidão. É o retrato da população que o cenário
    descreve, antes de a disciplina e a sorte entrarem.
    """
    students = generate_students(config, np.random.default_rng(SAMPLE_SEED))
    aptitudes = draw_aptitudes(
        students, config.disciplines, config, np.random.default_rng(SAMPLE_SEED)
    )
    grades = [
        grade_for_attempt(
            aptitude=aptitude,
            difficulty=1.0,
            relative_utility=1.0,
            attempt=1,
            utility_gain=0.0,
            retake_gain=1.0,
        )
        for aptitude in aptitudes.values()
    ]
    return grade_histogram(grades)


def arm_config(config: SimulationConfig, *, arm: Arm, seed: int) -> SimulationConfig:
    """O cenário como um braço o roda: as quatro escolhas do braço e a seed.

    É o **único** lugar em que um braço vira configuração, e é o que torna o
    traço de uma execução conferível: a tela individual pede a mesma
    `(braço, seed)` que o boxplot resumiu e recebe a simulação idêntica, porque
    a configuração passa por aqui dos dois lados.
    """
    return dataclasses.replace(
        config,
        mechanism=arm.mechanism,
        credit_return=arm.credit_return,
        resolver=arm.resolver,
        credit_memory=arm.credit_memory,
        seed=seed,
    )


def _run_one(config: SimulationConfig, arm: Arm, seed: int) -> RunSummary:
    return summarize(run_simulation(arm_config(config, arm=arm, seed=seed)), seed=seed)


def run_comparison(
    config: SimulationConfig, *, runs: int, workers: int = 4
) -> ComparisonResult:
    """Roda `runs` simulações em cada braço, com as seeds de 1 a `runs`.

    Três campos do cenário recebido são ignorados de propósito. A **seed**,
    porque numa comparação ela deixa de ser parâmetro e passa a ser o eixo da
    amostra. E o **resolvedor** e a **política de retorno**, porque são eixos
    do experimento: os braços os impõem. O resto — disciplinas, população,
    horizonte, rodadas — vale igual em todos, que é o que torna a diferença
    atribuível ao modelo.

    As execuções saem em paralelo por `ThreadPoolExecutor`, e não por processos:
    o tempo do leilão está quase todo dentro do CBC, que roda como processo
    externo e devolve a GIL enquanto se espera por ele. Threads também evitam
    reimportar numpy e pulp em cada worker, que custaria mais do que a
    simulação. A ordem das seeds é preservada, de modo que o i-ésimo elemento
    de cada lista é a mesma população.
    """
    if not 1 <= runs <= MAX_RUNS:
        raise ValueError(f"o número de execuções deve estar entre 1 e {MAX_RUNS}")
    seeds = list(range(1, runs + 1))

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        jobs = [
            [pool.submit(_run_one, config, arm, seed) for seed in seeds] for arm in ARMS
        ]
    return ComparisonResult(
        runs=runs,
        utility_distribution=sample_distribution(config),
        grade_distribution=sample_grade_distribution(config),
        arms=[
            ArmResult(
                key=arm.key,
                mechanism=arm.mechanism,
                credit_return=arm.credit_return,
                runs=[job.result() for job in arm_jobs],
            )
            for arm, arm_jobs in zip(ARMS, jobs)
        ],
    )
