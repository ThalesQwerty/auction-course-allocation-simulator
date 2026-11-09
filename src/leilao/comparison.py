"""Comparação entre os modelos de alocação (Seção 7.3).

O anteprojeto impõe duas condições metodológicas à comparação, e este módulo
existe para fazer as duas valerem de uma vez:

1. **Mesma inicialização dos dois lados.** "Sempre que os mecanismos forem
   comparados entre si, ambos serão inicializados com a mesma configuração de
   parâmetros iniciais, tais como alunos, cursos, períodos, disciplinas,
   utilidades, notas, entre outros." Como tudo isso é derivado da seed, basta
   rodar o mesmo cenário com a mesma seed nos dois mecanismos — é literalmente
   a mesma população, o mesmo interesse e a mesma matriz de notas
   encontrando regras de alocação diferentes.
2. **Múltiplas configurações de entrada.** "Serão testadas múltiplas
   configurações de entrada diferentes para cada comparação, e o resultado
   médio das simulações será avaliado." As seeds de 1 a N são essas
   configurações: N populações diferentes, cada uma vista pelos dois
   mecanismos.

Juntas, as duas isolam o nexo causal no mecanismo. Uma simulação só não diria
nada — a diferença poderia ser daquela população; e N simulações sem parear as
seeds mediriam a variação entre populações junto da variação entre mecanismos.

**São dois braços** (`ARMS`): a ordenação por CR e o leilão com retorno. A
complexidade do trabalho foi para os parâmetros — os perfis de aluno e a
disponibilidade —, e por equilíbrio saiu dos modelos comparados.

O preço disso é que o vão medido soma três mudanças ao mesmo tempo, e não diz
qual pesou. A escada que as separava continua aqui, em `ABLATION_ARMS`:

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

**Uma simulação vira um número por métrica**, que é a linha das tabelas. Para as
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
não é: é propriedade da simulação inteira, a média de quantos períodos cada
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

from .behavior import draw_interest
from .equations import (
    RequestStates,
    grade_for_attempt,
    grade_histogram,
    interest_histogram,
    weighted_mean,
)
from .equations import time_to_graduate as mean_span
from .grading import GradeShapes, draw_base_quantiles
from .config import (
    CreditMemory,
    CreditReturnPolicy,
    Mechanism,
    Resolver,
    SimulationConfig,
)
from .metrics import Metrics
from .population import generate_students
from .simulation import GroupSnapshot, SimulationResult, run_simulation

# Teto de simulações por braço. Não é limitação técnica: é que a faixa para de
# ganhar informação muito antes disso, e cada simulação a mais custa uma
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
# **Só entra aqui o que sai nos resultados**: cada braço é um traçado dos
# gráficos e uma linha das tabelas, e nada roda para não ser mostrado. Duas
# células que já foram braços saíram por não serem passos do caminho — o CR
# resolvido por PLI (que tem defeito declarado: como todo pedido do aluno tem
# o mesmo peso N_a, a PLI é indiferente sobre qual cortar, e o aluno não tem
# voz sobre o que perde) e o leilão sem sobra. As duas seguem alcançáveis por
# `SimulationConfig` — `resolver="ilp"` com `mechanism="ranking"`, e
# `credit_memory="none"` — se um dia forem precisas para um apêndice.
ARMS: tuple[Arm, ...] = (
    Arm("ranking_greedy", "ranking", "none", resolver="greedy"),
    Arm("credits_return", "credits", "ratio"),
)

# Os dois degraus do meio do caminho, que **não** rodam por padrão.
#
# Eles separam o vão em três parcelas — mensagem (CR → lance), resolução
# (varredura → PLI) e retorno —, e sem eles o que a comparação mede é a soma
# das três, sem dizer qual pesou. Saíram do padrão porque o trabalho passou a
# comparar dois modelos, e a escada inteira não cabe no texto; ficam aqui
# porque custam tempo de execução e não complexidade conceitual — são a mesma
# simulação com dois campos trocados. Para a ablação, `run_comparison(...,
# arms=ARMS + ABLATION_ARMS)`.
#
# `credits_greedy` é o *bidding points* clássico — orçamento de pontos, lances
# por disciplina, disciplina fechando no menor lance atendido (Sönmez & Ünver
# 2010, sobre Michigan e Yale SOM). Não confundir com o **Course Match** de
# Wharton, que substituiu o bidding points de lá: aquele é cardinal e resolve
# por MIP, mas é outro mecanismo — preferências sobre *cestas*, orçamentos
# aproximadamente iguais e preços de equilíbrio, não lance pago a segundo
# preço. É trabalho relacionado, não célula deste desenho.
ABLATION_ARMS: tuple[Arm, ...] = (
    Arm("credits_greedy", "credits", "none", resolver="greedy"),
    Arm("credits_ilp", "credits", "none", resolver="ilp"),
)


# Os braços por chave — como a interface se refere a um deles ao pedir o traço
# de uma simulação. Inclui a ablação: o traço de um braço que não rodou por
# padrão continua reproduzível.
ARM_BY_KEY: dict[str, Arm] = {arm.key: arm for arm in ARMS + ABLATION_ARMS}


def arms_from_keys(keys: list[str]) -> tuple[Arm, ...]:
    """Os braços que essas chaves nomeiam, na ordem canônica de `ARM_BY_KEY`.

    A ordem em que as chaves chegam é ignorada de propósito: a tela acha o
    braço pela chave, e fixar a ordem aqui faz o resumo sair idêntico seja
    qual for a ordem do pedido. Chave repetida entra uma vez só.

    Existe porque rodar **um** braço é o caso comum enquanto se mexe no
    cenário: a comparação custa uma simulação completa por braço e por seed, e
    quem está calibrando a grade não precisa do outro lado a cada tentativa.
    O que sai daqui serve direto em `run_comparison(..., arms=...)` — a
    resposta traz menos braços, e a tela desenha o que veio.
    """
    wanted = set(keys)
    unknown = sorted(wanted - ARM_BY_KEY.keys())
    if unknown:
        raise ValueError(f"braço desconhecido: {', '.join(unknown)}")
    chosen = tuple(arm for key, arm in ARM_BY_KEY.items() if key in wanted)
    if not chosen:
        raise ValueError("escolha ao menos um braço para comparar")
    return chosen


@dataclass(frozen=True)
class PeriodSeries:
    """As métricas de período de uma simulação, sem reduzir.

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
    propriedade da simulação inteira. A versão por período — quanto levou quem
    concluiu em t — seria outra grandeza, com viés de sobrevivência, porque
    quem conclui cedo é rápido por construção.
    """

    period: list[int]
    students: list[int]
    # A fração de concluintes **acumulada**: quem já concluiu até o fim do
    # período sobre quem já tinha ingressado. Sobe ao longo do horizonte, e no
    # último período é a fração final.
    graduation_rate: list[float]
    efficiency: list[float]
    utilization: list[float]
    fidelity: list[float]
    fairness: list[float]
    correlation: list[float]
    # A fração das vagas obtidas que foi largada — ver `equations.exclusion_rate`.
    exclusion_rate: list[float]
    # Os seis estados de solicitação, em média por aluno. É a série da seção
    # "Solicitações de disciplinas": uma linha por estado, não empilhada, cada
    # braço no seu painel.
    request_states: list[RequestStates]
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
class GroupSeries:
    """A `PeriodSeries` de um grupo de um recorte — uma coorte ou um perfil.

    O eixo continua sendo o período: o que muda é sobre quem a métrica corre.
    O recorte particiona a população, então os grupos de um mesmo eixo somam o
    agregado em cada período.
    """

    group: str
    series: PeriodSeries


# Os recortes da tela, na ordem do seletor. `cohort` é o período de ingresso;
# os outros quatro são os eixos de perfil (`simulation.Axis.profiles`).
CUT_AXES: tuple[str, ...] = (
    "cohort",
    "performance",
    "availability",
    "selectivity",
    "concentration",
)


@dataclass(frozen=True)
class GroupBands:
    """Um grupo de um recorte reduzido **entre as seeds**, período a período.

    Cada grandeza vira `(q1, mediana, q3)` em cada período — o que o gráfico
    desenha como linha e faixa. A redução acontece aqui, e não na tela, porque
    a amostra inteira (seed × grupo × período) não cabe no histórico do
    navegador; a mediana e os quartis cabem, e não dependem de N.

    `n` é quantas seeds mediram o grupo naquele período. Na cauda do horizonte
    parte delas já esvaziou, e ali a amostra não é a mesma do começo do eixo.
    """

    group: str
    period: list[int]
    n: list[int]
    # Uma lista paralela a `period` por grandeza. `None` onde nenhuma seed
    # mediu aquela grandeza no período (uma rodada que não aconteceu).
    values: dict[str, list[tuple[float, float, float] | None]]


@dataclass(frozen=True)
class AxisBands:
    """Os grupos de um recorte, na ordem em que o cenário os declara.
    `overall` é a universidade inteira, com um grupo só."""

    axis: str
    groups: list[GroupBands]


@dataclass(frozen=True)
class RunSummary:
    """Uma simulação reduzida a um ponto por métrica.

    `periods` é quantos períodos a simulação de fato publicou — pode ser menor
    que |T| se a população se esvaziou antes do horizonte —, e serve para
    conferir que todos os braços viveram o mesmo intervalo. `graduates` é o
    contexto sem o qual `time_to_graduate` não se lê.
    """

    seed: int
    periods: int
    graduates: int  # quantos concluíram o curso — eq. (40)
    # Quantos foram **jubilados**: esgotaram os períodos de residência sem
    # fechar a grade. Com `graduates`, reparte `population` em três — saiu por
    # cima, saiu por baixo, e (só se o horizonte não esgotou) continua em curso.
    dismissed: int
    # Quantos ingressaram ao todo, que é o denominador das duas frações. Sem
    # ele os dois números acima são contagens sem escala: 40 formados é muito
    # ou pouco conforme a coorte tenha 60 ou 600 pessoas.
    population: int
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
    # Desperdício: a fração das vagas obtidas que foi largada antes de virar
    # aula. É a quinta métrica da comparação — e a que a disponibilidade
    # existe para produzir. Ver `equations.exclusion_rate`.
    exclusion_rate: float
    # Os seis estados em média por aluno, reduzidos a um ponto cada. A série
    # sem reduzir está em `by_period` e `by_group`.
    request_states: RequestStates
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
    # A mesma série por período, um grupo de cada vez, para cada recorte de
    # `CUT_AXES`. É o material das faixas do braço (`ArmResult.series`).
    by_group: dict[str, list[GroupSeries]]


@dataclass(frozen=True)
class ArmResult:
    """As N simulações de um braço, na ordem das seeds."""

    key: str
    mechanism: Mechanism
    credit_return: CreditReturnPolicy
    runs: list[RunSummary]
    # As séries por período reduzidas entre as seeds: o agregado e cada
    # recorte. É o que os gráficos desenham — ver `bands`.
    series: list[AxisBands] = field(default_factory=list)


@dataclass(frozen=True)
class ComparisonResult:
    """As N simulações de cada braço, pareadas pela seed.

    Todas as listas têm o mesmo tamanho e a mesma ordem de seeds: o i-ésimo
    elemento de cada uma é a *mesma* população sob regras diferentes. Quem lê
    pode tanto tratar cada lista como uma amostra (é o que a faixa dos gráficos faz) quanto
    comparar par a par — e a comparação par a par é a que responde "o retorno
    mudou alguma coisa?", porque ali a população é literalmente a mesma.
    """

    runs: int
    arms: list[ArmResult]
    # As duas distribuições de entrada do cenário, para a tela mostrar de onde
    # vieram os números. Não variam entre braços nem entre seeds — são do
    # cenário, não da simulação.
    interest_distribution: list[float] = field(default_factory=list)
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


def weighted_states(pairs: list[tuple[Metrics, int]]) -> RequestStates:
    """A média ponderada dos seis estados, campo a campo.

    O peso é o mesmo das demais métricas — os alunos medidos —, de modo que um
    período final de vinte alunos não pesa como um período cheio. Instante sem
    os estados (uma rodada, onde a exclusão ainda não aconteceu) simplesmente
    não entra.
    """
    rows = [(m.request_states, w) for m, w in pairs if m.request_states is not None]
    if not rows:
        return RequestStates(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def of(field_name: str) -> float:
        return weighted_mean([(getattr(r, field_name), w) for r, w in rows]) or 0.0

    return RequestStates(
        not_eligible=of("not_eligible"),
        not_requested=of("not_requested"),
        refused=of("refused"),
        excluded=of("excluded"),
        failed=of("failed"),
        approved=of("approved"),
    )


def _measured(snapshot: GroupSnapshot | None) -> bool:
    """O recorte tem métrica: alguém, além dos calouros, disputou o instante."""
    return (
        snapshot is not None
        and snapshot.metrics is not None
        and snapshot.metrics.students > 0
    )


def _period_series(
    instants: list[tuple[int, GroupSnapshot | None, list[GroupSnapshot | None]]],
    rounds: int,
) -> PeriodSeries:
    """A série por período de um recorte.

    `instants` traz, para cada período, o recorte no fim dele e o mesmo
    recorte em cada rodada. Só entram os períodos em que o recorte foi medido
    — nem os vazios, nem aquele em que todo o grupo acabou de ingressar.
    """
    measured = [
        (period, snapshot, by_round)
        for period, snapshot, by_round in instants
        if _measured(snapshot)
    ]

    def series(of) -> list:
        return [of(snapshot.metrics) for _, snapshot, _ in measured]

    def saturation(by_round: list[GroupSnapshot | None]) -> list[float | None]:
        """Uma posição por rodada do cenário. Período que publicou menos
        rodadas é completado com `None`, para a coluna r ser a mesma rodada em
        todos os períodos."""
        row: list[float | None] = []
        for index in range(rounds):
            snapshot = by_round[index] if index < len(by_round) else None
            row.append(
                snapshot.metrics.allocations_per_student
                if _measured(snapshot)
                else None
            )
        return row

    return PeriodSeries(
        period=[period for period, _, _ in measured],
        students=series(lambda m: m.students),
        graduation_rate=[
            snapshot.graduated / snapshot.population if snapshot.population else 0.0
            for _, snapshot, _ in measured
        ],
        efficiency=series(lambda m: m.efficiency),
        utilization=series(lambda m: m.utilization),
        fidelity=series(lambda m: m.fidelity),
        fairness=series(lambda m: m.fairness),
        correlation=series(lambda m: m.correlation),
        exclusion_rate=series(lambda m: m.exclusion_rate or 0.0),
        request_states=series(
            lambda m: m.request_states or RequestStates(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        ),
        allocations_per_round=[saturation(by_round) for _, _, by_round in measured],
    )


def _cut(report, axis: str) -> list[GroupSnapshot]:
    """Os grupos de um recorte num instante."""
    return report.by_cohort if axis == "cohort" else report.by_profile.get(axis, [])


def group_series(result: SimulationResult) -> dict[str, list[GroupSeries]]:
    """A série por período de cada grupo de cada recorte de `CUT_AXES`.

    A ordem dos grupos é a de primeira aparição: a dos perfis é a do cenário,
    e a das coortes é a do ingresso.
    """
    rounds = max((len(period.rounds) for period in result.periods), default=0)
    out: dict[str, list[GroupSeries]] = {}
    for axis in CUT_AXES:
        order: list[str] = []
        for period in result.periods:
            for snapshot in _cut(period.aggregate, axis):
                if snapshot.group is not None and snapshot.group not in order:
                    order.append(snapshot.group)

        def find(report, group: str) -> GroupSnapshot | None:
            return next((s for s in _cut(report, axis) if s.group == group), None)

        out[axis] = [
            GroupSeries(
                group=group,
                series=_period_series(
                    [
                        (
                            period.period,
                            find(period.aggregate, group),
                            [find(report, group) for report in period.rounds],
                        )
                        for period in result.periods
                    ],
                    rounds,
                ),
            )
            for group in order
        ]
    return out


# As grandezas de uma faixa, na ordem em que a tela as lê. As seis de estado
# levam o nome do estado; as de saturação, `round_<r>`.
STATE_KEYS: tuple[str, ...] = (
    "not_eligible",
    "not_requested",
    "refused",
    "excluded",
    "failed",
    "approved",
)


def _quantities(series: PeriodSeries, index: int) -> dict[str, float | None]:
    """O que um período de uma série mede, grandeza a grandeza."""
    states = series.request_states[index]
    values: dict[str, float | None] = {
        "students": float(series.students[index]),
        "graduation_rate": series.graduation_rate[index],
        "efficiency": series.efficiency[index],
        "utilization": series.utilization[index],
        "fidelity": series.fidelity[index],
        "fairness": series.fairness[index],
        "correlation": series.correlation[index],
        "exclusion_rate": series.exclusion_rate[index],
    }
    for key in STATE_KEYS:
        values[key] = getattr(states, key)
    for r, value in enumerate(series.allocations_per_round[index], start=1):
        values[f"round_{r}"] = value
    return values


def _quartiles(values: list[float]) -> tuple[float, float, float]:
    """`(q1, mediana, q3)` por interpolação linear — o método 7, o mesmo do
    `quantile` da interface e o padrão do numpy.

    Quatro casas: a tela mostra no máximo três, e a resposta inteira vai para
    o histórico do navegador, onde cada casa a mais custa espaço."""
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    return (round(float(q1), 4), round(float(median), 4), round(float(q3), 4))


def _group_bands(group: str, samples: list[PeriodSeries]) -> GroupBands:
    """Reduz as séries de um grupo, uma por seed, a quartis por período."""
    by_period: dict[int, list[dict[str, float | None]]] = defaultdict(list)
    for series in samples:
        for index, period in enumerate(series.period):
            by_period[period].append(_quantities(series, index))
    periods = sorted(by_period)
    keys: list[str] = []
    for period in periods:
        for row in by_period[period]:
            keys.extend(k for k in row if k not in keys)

    def band(period: int, key: str) -> tuple[float, float, float] | None:
        values = [
            row[key] for row in by_period[period] if row.get(key) is not None
        ]
        return _quartiles(values) if values else None

    return GroupBands(
        group=group,
        period=periods,
        n=[len(by_period[period]) for period in periods],
        values={key: [band(period, key) for period in periods] for key in keys},
    )


def bands(runs: list[RunSummary]) -> list[AxisBands]:
    """As séries de um braço reduzidas entre as seeds, recorte a recorte.

    O primeiro é `overall`, a universidade inteira; depois os de `CUT_AXES`.
    Um grupo que falte numa seed (coorte que não chegou a ser medida) entra
    com as seeds que o têm.
    """
    out = [AxisBands("overall", [_group_bands("overall", [r.by_period for r in runs])])]
    for axis in CUT_AXES:
        order: list[str] = []
        samples: dict[str, list[PeriodSeries]] = defaultdict(list)
        for run in runs:
            for entry in run.by_group.get(axis, []):
                if entry.group not in order:
                    order.append(entry.group)
                samples[entry.group].append(entry.series)
        out.append(
            AxisBands(axis, [_group_bands(group, samples[group]) for group in order])
        )
    return out


def summarize(result: SimulationResult, *, seed: int) -> RunSummary:
    """Reduz uma simulação inteira a um ponto por métrica.

    As três de período passam pela média ponderada pelos alunos medidos; o tempo
    de formatura é da simulação inteira; a saturação é uma média dessas por
    rodada. O ponto não substitui o material de que saiu: `by_period` leva as
    mesmas métricas sem reduzir, e as duas leituras ficam conferíveis uma contra
    a outra. `by_group` leva a mesma série por grupo de cada recorte.

    Períodos sem métrica não entram — nem os vazios, nem aquele em que todo
    mundo acabou de ingressar. Um zero ali seria um período em que ninguém ficou
    satisfeito, que é coisa diferente de um período que não se mede.
    """
    graduates = sum(1 for s in result.students if s.graduated_at is not None)
    dismissed = sum(1 for s in result.students if s.dismissed_at is not None)
    rounds = max((len(period.rounds) for period in result.periods), default=0)
    by_period = _period_series(
        [
            (
                period.period,
                period.aggregate.overall,
                [report.overall for report in period.rounds],
            )
            for period in result.periods
        ],
        rounds,
    )
    weights = by_period.students

    def mean(values: list[float]) -> float:
        return weighted_mean(list(zip(values, weights))) or 0.0

    states = [
        (metrics, metrics.students)
        for period in result.periods
        for metrics in [period.aggregate.overall.metrics]
        if _measured(period.aggregate.overall)
    ]

    return RunSummary(
        seed=seed,
        periods=len(result.periods),
        graduates=graduates,
        dismissed=dismissed,
        population=len(result.students),
        efficiency=mean(by_period.efficiency),
        utilization=mean(by_period.utilization),
        fidelity=mean(by_period.fidelity),
        fairness=mean(by_period.fairness),
        correlation=mean(by_period.correlation),
        exclusion_rate=mean(by_period.exclusion_rate),
        request_states=weighted_states(states),
        time_to_graduate=time_to_graduate(result),
        allocations_per_round=allocations_per_round(result),
        by_period=by_period,
        by_group=group_series(result),
    )


# A seed da amostra dos histogramas. É a **primeira da comparação**, e não a do
# cenário: numa comparação a seed do cenário é ignorada (ela vira o eixo da
# amostra), e usar `config.seed` faria dois cenários idênticos a menos da seed
# devolverem resultados diferentes — justamente o que a comparação promete que
# não acontece. Com 1, o histograma descreve literalmente a primeira população
# que a comparação rodou.
SAMPLE_SEED = 1


def sample_interest_distribution(config: SimulationConfig) -> list[float]:
    """O histograma de interesse do cenário, sorteado à parte da simulação.

    Descreve a **entrada**, não o resultado: a mesma distribuição que a
    simulação usa, numa amostra própria. Vem daqui, e não de uma simulação,
    porque numa comparação há 3N matrizes, todas da mesma distribuição, sem uma
    que seja "a" certa. (Na execução única, ao contrário, o histograma sai da
    matriz que a simulação de fato usou.)
    """
    students = generate_students(config, np.random.default_rng(SAMPLE_SEED))
    rows = draw_interest(students, config, np.random.default_rng(SAMPLE_SEED))
    return interest_histogram(rows.values())


def sample_grade_distribution(config: SimulationConfig) -> list[float]:
    """O histograma de notas de primeira tentativa, pelo mesmo motivo e do mesmo
    jeito que `sample_interest_distribution`.

    A nota mostrada é a de **primeira tentativa em disciplina de dificuldade
    1**, que é a situação que os três parâmetros do perfil descrevem. É o
    retrato da população que o cenário declara, antes de a grade entrar.
    """
    students = generate_students(config, np.random.default_rng(SAMPLE_SEED))
    quantiles = draw_base_quantiles(
        students, config.disciplines, config, np.random.default_rng(SAMPLE_SEED)
    )
    shapes = GradeShapes()
    by_id = {student.id: student for student in students}

    def grade(student_id: str, quantile: float) -> float:
        mode, left_sd, right_sd = shapes.of(by_id[student_id].performance, 1.0, 1)
        return grade_for_attempt(
            quantile=quantile, mode=mode, left_sd=left_sd, right_sd=right_sd
        )

    grades = [
        grade(student_id, quantile)
        for (student_id, _), quantile in quantiles.items()
    ]
    return grade_histogram(grades)


def arm_config(config: SimulationConfig, *, arm: Arm, seed: int) -> SimulationConfig:
    """O cenário como um braço o roda: as quatro escolhas do braço e a seed.

    É o **único** lugar em que um braço vira configuração, e é o que torna o
    traço de uma simulação conferível: a tela individual pede a mesma
    `(braço, seed)` que a comparação resumiu e recebe a simulação idêntica, porque
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
    config: SimulationConfig,
    *,
    runs: int,
    workers: int = 4,
    arms: tuple[Arm, ...] = ARMS,
) -> ComparisonResult:
    """Roda `runs` simulações em cada braço, com as seeds de 1 a `runs`.

    `arms` é o conjunto comparado, e o padrão são os dois do trabalho. Para a
    ablação que separa mensagem, resolução e retorno, passe
    `arms=ARMS + ABLATION_ARMS` — custa uma simulação a mais por braço e por
    seed, e nada mais.

    Três campos do cenário recebido são ignorados de propósito. A **seed**,
    porque numa comparação ela deixa de ser parâmetro e passa a ser o eixo da
    amostra. E o **resolvedor** e a **política de retorno**, porque são eixos
    do experimento: os braços os impõem. O resto — disciplinas, população,
    horizonte, rodadas — vale igual em todos, que é o que torna a diferença
    atribuível ao modelo.

    As simulações saem em paralelo por `ThreadPoolExecutor`, e não por processos:
    o tempo do leilão está quase todo dentro do CBC, que roda como processo
    externo e devolve a GIL enquanto se espera por ele. Threads também evitam
    reimportar numpy e pulp em cada worker, que custaria mais do que a
    simulação. A ordem das seeds é preservada, de modo que o i-ésimo elemento
    de cada lista é a mesma população.
    """
    if not 1 <= runs <= MAX_RUNS:
        raise ValueError(f"o número de simulações deve estar entre 1 e {MAX_RUNS}")
    seeds = list(range(1, runs + 1))

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        jobs = [
            [pool.submit(_run_one, config, arm, seed) for seed in seeds] for arm in arms
        ]
    return ComparisonResult(
        runs=runs,
        interest_distribution=sample_interest_distribution(config),
        grade_distribution=sample_grade_distribution(config),
        arms=[
            ArmResult(
                key=arm.key,
                mechanism=arm.mechanism,
                credit_return=arm.credit_return,
                runs=summaries,
                series=bands(summaries),
            )
            for arm, arm_jobs in zip(arms, jobs)
            for summaries in [[job.result() for job in arm_jobs]]
        ],
    )
