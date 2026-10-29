"""Comparação entre os dois mecanismos (Seção 7.3).

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

**São três braços, não dois** (`ARMS`). O leilão entra duas vezes, com e sem
retorno de créditos, porque o retorno é o que pode devolver ao mecanismo algum
senso meritocrático: na política proporcional o aluno recupera a fatia do preço
correspondente à nota, de modo que ir bem compra poder de compra no período
seguinte. A ordenação por CR faz isso por construção — o histórico *é* o
critério —, e o leilão sem retorno não faz de jeito nenhum. Os três juntos
mostram onde a política cai entre os dois extremos.

Por isso a política de retorno **não é parâmetro do cenário aqui**: ela é o eixo
do experimento, e o `credit_return` que vier na configuração é ignorado, como a
seed. Cada braço impõe o seu.

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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np

from .behavior import draw_utilities, utility_distribution
from .grading import draw_aptitudes, grade_distribution, grade_for_attempt
from .config import (
    CreditMemory,
    CreditReturnPolicy,
    Mechanism,
    Resolver,
    SimulationConfig,
)
from .population import generate_students
from .simulation import SimulationResult, run_simulation

# Teto de execuções por braço. Não é limitação técnica: é que o boxplot para de
# ganhar informação muito antes disso, e cada execução a mais custa uma
# simulação inteira em cada um dos três braços.
MAX_RUNS = 100



# A faixa em que sigma diz alguma coisa. Abaixo do piso a linha do aluno é
# praticamente uniforme e os dois mecanismos convergem; acima do teto ele quer
# uma disciplina só e ninguém se forma. Nada é recusado fora disso — a
# simulação continua correta —, mas é a faixa que a interface sugere.
USEFUL_SIGMA_RANGE = (0.25, 3.0)


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


# Os três braços, na ordem em que entram no eixo e na legenda: a linha de base
# primeiro, e depois o leilão com e sem retorno. Pô-los nessa ordem faz a
# correlação (eq. 57) ser lida de uma vez — do mecanismo em que o CR é o próprio
# critério ao que o ignora por completo, com o retorno no meio.
ARMS: tuple[Arm, ...] = (
    # As quatro células do cruzamento moeda x resolvedor. As duas de fora da
    # diagonal são mecanismos reais: "lance + varredura" é o *bidding points*
    # dos business schools, o mais implantado do mundo, e "CR + PLI" é a
    # matrícula por histórico resolvida globalmente.
    #
    # Os dois resolvedores só divergem onde a carga horária aperta — sem ela o
    # problema se separa por disciplina e a varredura é ótima. É por isso que o
    # eixo só passou a ter conteúdo depois das optativas, que fazem o conjunto
    # elegível passar de W_a.
    Arm("ranking_greedy", "ranking", "none", resolver="greedy"),
    Arm("ranking_ilp", "ranking", "none", resolver="ilp"),
    Arm("credits_greedy", "credits", "none", resolver="greedy"),
    Arm("credits_ilp", "credits", "none", resolver="ilp"),
    # A escada de acúmulo, sobre o leilão com PLI. O degrau do meio é o
    # `credits_ilp` acima, então só faltam as duas pontas: sem memória nenhuma
    # e com memória das duas fontes.
    #
    # Ela é um eixo só — **quanta memória o orçamento tem** —, e o degrau do
    # meio é o que separa as duas fontes, que têm sinais opostos de incentivo:
    # a sobra premia quem pagou barato, o retorno premia quem aprovou.
    Arm("credits_no_memory", "credits", "none", credit_memory="none"),
    Arm("credits_return", "credits", "ratio"),
)


@dataclass(frozen=True)
class RunSummary:
    """Uma execução reduzida a um ponto por métrica.

    `periods` é quantos períodos a simulação de fato publicou — pode ser menor
    que |T| se a população se esvaziou antes do horizonte —, e serve para
    conferir que os dois mecanismos viveram o mesmo intervalo. `graduates` é o
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
    """Períodos do ingresso ao diploma, na média dos concluintes.

    Conta inclusive o período da formatura: quem entra em t e conclui ao fim de
    t levou 1 período, não 0. Quem não concluiu não tem tempo — e não entra
    como "muito lento", porque não há valor que o represente; é `graduates` que
    diz quantos ficaram de fora.
    """
    spans = [
        s.graduated_at - s.entry_period + 1
        for s in result.students
        if s.graduated_at is not None
    ]
    return sum(spans) / len(spans) if spans else None


def _weighted(pairs: list[tuple[float, int]]) -> float | None:
    """Média ponderada de (valor, peso). `None` quando não há o que promediar —
    um zero ali seria um valor medido, e não a ausência de medida."""
    total = sum(weight for _, weight in pairs)
    if not total:
        return None
    return sum(value * weight for value, weight in pairs) / total


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
            _weighted(
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


def summarize(result: SimulationResult, *, seed: int) -> RunSummary:
    """Reduz uma simulação inteira a um ponto por métrica.

    As três de período passam pela média ponderada pelos alunos medidos; o tempo
    de formatura é da execução inteira; a saturação é uma média dessas por
    rodada.

    Períodos sem métrica não entram — nem os vazios, nem aquele em que todo
    mundo acabou de ingressar. Um zero ali seria um período em que ninguém ficou
    satisfeito, que é coisa diferente de um período que não se mede.
    """
    graduates = sum(1 for s in result.students if s.graduated_at is not None)
    by_period = [
        (period.aggregate.overall.metrics, period.aggregate.overall.metrics.students)
        for period in result.periods
        if period.aggregate.overall.metrics is not None
        and period.aggregate.overall.metrics.students > 0
    ]

    def mean(of) -> float:
        return _weighted([(of(m), w) for m, w in by_period]) or 0.0

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
    return utility_distribution(rows)


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
            coupling=0.0,
            noise=0.0,
            noise_sigma=0.0,
        )
        for aptitude in aptitudes.values()
    ]
    return grade_distribution(grades)


def _run_one(config: SimulationConfig, arm: Arm, seed: int) -> RunSummary:
    return summarize(
        run_simulation(
            dataclasses.replace(
                config,
                mechanism=arm.mechanism,
                credit_return=arm.credit_return,
                resolver=arm.resolver,
                credit_memory=arm.credit_memory,
                seed=seed,
            )
        ),
        seed=seed,
    )


def run_comparison(
    config: SimulationConfig, *, runs: int, workers: int = 4
) -> ComparisonResult:
    """Roda `runs` simulações de cada braço, com as seeds de 1 a `runs`.

    Dois campos do cenário recebido são ignorados de propósito. A **seed**,
    porque numa comparação ela deixa de ser parâmetro e passa a ser o eixo da
    amostra. E a **política de retorno**, porque ela é o eixo do experimento: os
    braços a impõem. O resto — disciplinas, perfis, horizonte, rodadas — vale
    igual nos três, que é o que torna a diferença atribuível ao modelo.

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
