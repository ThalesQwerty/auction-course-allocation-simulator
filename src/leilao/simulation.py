"""Simulação multi-período da matrícula universitária (Seção 7.2).

Amarra as peças: a cada período letivo t sorteia-se a matriz de utilidades dos
alunos ativos, roda-se |R| rodadas de leilão (motor da Seção 7.1, reaproveitado
tal e qual), e ao fim do período saem as notas, o retorno de créditos e as
conclusões de curso.

    para cada período t:
        u^(t)                                      eqs. (41)-(43)
        matrícula garantida dos ingressantes       (fora do leilão)
        para cada rodada r:
            c^(t,r) <- u^(t), C^(t,r), B_a^(t,r)   eqs. (44)-(46)
            z^(t,r) <- leilão(c^(t,r))             eqs. (22)-(25)
            q, W, C                                eqs. (13), (14), (27)
        notas, retorno de créditos                 eqs. (33)-(36)
        conclusão de curso                         eq. (40)

Não há cursos: a universidade inteira cursa a mesma grade, e toda disciplina é
obrigatória — concluir é aprovar em todas. Os relatórios recortam a população
por três eixos (`_Axis`), que são a mesma gente partida de formas diferentes: a
**geração** (quem ingressou num mesmo período, t_a da eq. 31) e os dois perfis
do aluno, **aptidão** e **afinidade**. Somar qualquer um deles reproduz o
agregado.

**Quem ingressa não disputa.** O aluno novo recebe vaga garantida em todas as
disciplinas de 1º período — as sem pré-requisito — e fica de fora do leilão
naquele período. O sistema lança na conta dele o gasto correspondente,
repartindo o orçamento igualmente entre essas disciplinas (o resto da divisão
continua no saldo), e é esse valor que alimenta o retorno de créditos da
eq. (34). Vale só no período de ingresso: recursar uma dessas disciplinas é
disputá-la no leilão como qualquer outra.

O aluno sai do conjunto ativo por uma única porta: concluindo o curso (eq. 40).
Quem não concluiu continua disputando até o fim do horizonte, e é a fase de
drenagem que dá às gerações tardias tempo de chegar lá.

**Dois mecanismos, um cenário.** `config.mechanism` troca só o miolo da rodada:
o leilão por créditos da Seção 7.1 (`credits`) ou a ordenação por CR da
Seção 7.3.1 (`ranking`, módulo `ranking`). Tudo o mais — população, utilidades,
notas, pré-requisitos, matrícula garantida, conclusão e métricas — é idêntico,
que é a condição metodológica da Seção 7.3: os dois lados partem da mesma
inicialização, e por isso a diferença entre eles é atribuível ao mecanismo.
Sem crédito não há orçamento, preço nem retorno, e essas grandezas saem `None`
dos relatórios — ver `SimulationConfig.uses_credits`.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from .auction import AuctionInput, Bid, run_auction
from .behavior import compute_bids, draw_utilities, utility_matrix
from .config import SimulationConfig
from .entities import Agent, Good
from .grading import credit_return, grade_for_attempt, initial_grades
from .metrics import Metrics, compute_metrics, demand_per_seat, satisfaction, semestralization
from .population import Student, generate_students
from .ranking import allocate_by_ranking, request_set
from .tie_breaking import stochastic_perturbations

# `RequestRecord.won_round` quando a vaga não veio de rodada nenhuma: é a
# matrícula garantida do ingressante, concedida antes do leilão abrir.
GUARANTEED_ROUND = 0


@dataclass(frozen=True)
class GroupSnapshot:
    """Recorte de alunos num instante da simulação — a unidade dos gráficos.

    Quando o recorte não tem ninguém no período (`active == 0`), as médias são
    `None` em vez de 0,0: não havia ninguém, o que é diferente de ninguém ter
    ficado satisfeito. Zero ali seria um ponto falso no gráfico e puxaria para
    baixo qualquer média feita sobre os períodos.

    **O calouro conta como gente, não como dado.** Quem ingressa no período não
    disputou nada: recebeu vaga garantida em todas as disciplinas de 1º período,
    que são exatamente as elegíveis para ele. Entra, portanto, com psi = 1,000 e
    CR = 0,000 — *sempre*, sem exceção —, e medir o mecanismo sobre esse ponto é
    medir a matrícula garantida, que é igual nos dois mecanismos. No preset
    Computação ele é 11% de todas as linhas aluno-período, e sozinho invertia o
    sinal da correlação da eq. (57): -0,09 com ele, +0,04 sem.

    Por isso ele fica de fora de **toda média por aluno** — as métricas e as
    grandezas de crédito —, e permanece nas **contagens de pessoas**:
    `active`, `population` e `graduated`. Daí `metrics.students <= active`, e o
    primeiro período de uma simulação não tem métrica nenhuma: ali todo mundo é
    calouro.
    """

    # Quem é este recorte: `None` na universidade inteira
    # (`RoundReport.overall`), o período de ingresso (t_a, eq. 31) em
    # `by_cohort`, e o nome do perfil em `by_aptitude` e `by_affinity`. É texto
    # porque os três eixos dividem a mesma estrutura — trocar a agregação de um
    # gráfico é trocar de lista, nada mais —, e só a lista de origem diz como
    # ler a chave.
    group: str | None
    metrics: Metrics | None
    active: int  # |A^(t)| do recorte no início do período
    # Alunos do recorte que já ingressaram, tenham concluído ou não. Não é
    # `active + graduated`: quem se forma ao fim de t conta nos dois lados dessa
    # soma, porque disputou o período inteiro antes de sair. É sobre este número
    # que se tira a fração de formados.
    population: int
    graduated: int  # concluintes acumulados até aqui
    mean_credits: float | None  # orçamento médio C_a ao fim do recorte
    mean_approved_hours: float | None
    # Economia de créditos do recorte, medida sobre a oferta do início do
    # período (C_a^(t,1), antes de qualquer lance) — distinta de `mean_credits`,
    # que é o que sobrou. `credits_per_seat` divide essa oferta pelas vagas de
    # toda a universidade: é o preço que uma vaga teria se todo o crédito em
    # mãos fosse gasto, e a soma das gerações dá o preço esperado global.
    credits_per_student: float | None
    credits_per_seat: float | None
    # Créditos apostados no período por aluno ativo, somando as rodadas. Pode
    # passar do orçamento: lance perdido não consome nada (eq. 25), então o
    # crédito que não virou vaga volta a ser apostado na rodada seguinte. A
    # matrícula garantida do ingressante entra aqui pelo valor que o sistema
    # lançou na conta dele, para que lance e gasto continuem na mesma régua.
    mean_bids: float | None
    # Retorno de créditos do período (soma de gamma_{a,x}, eq. 34), por aluno
    # ativo. Só existe no recorte de fim de período: em plena rodada as notas
    # ainda não saíram, e ali o campo vem `None` — não 0,0, que se leria como
    # "a política não devolveu nada".
    mean_credit_return: float | None


@dataclass(frozen=True)
class _Axis:
    """Um eixo de recorte: como rotular cada aluno e em que ordem as séries
    saem. Os três (geração, aptidão, afinidade) particionam a mesma população,
    então o relatório os trata pela mesma estrutura — o que muda de um para o
    outro é só a chave e a ordem."""

    key: Callable[[Student], str]
    order: list[str]


@dataclass(frozen=True)
class PriceStats:
    """Dispersão de pi_x (eq. 24) entre as disciplinas num instante.

    O preço não é grandeza de aluno nem de geração: é do mercado. O que se lê
    dele ao longo do tempo é a faixa — a disciplina mais cara, a média e a mais
    barata —, porque uma média sozinha esconde se o crédito está concentrado em
    poucas disputas ou espalhado por todas.
    """

    min: float
    mean: float
    max: float


@dataclass(frozen=True)
class _RoundState:
    """O que muda de uma rodada para a outra dentro de um período.

    O relatório de cada rodada só é montado depois do laço, quando a
    concorrência do período — que depende dos lances de *todas* as rodadas — já
    existe; até lá, o que varia fica guardado aqui.
    """

    number: int
    satisfaction: dict[str, float]
    won: dict[str, set[str]]
    budget: dict[str, int]
    bids: dict[str, int]  # acumulado até esta rodada, como o gasto
    prices: PriceStats | None


@dataclass(frozen=True)
class RoundReport:
    """Um ponto da série temporal: uma rodada, ou o agregado de um período."""

    period: int  # t
    round: int  # r; 0 identifica o agregado (t, *)
    # A universidade inteira (`group is None`).
    overall: GroupSnapshot
    # O mesmo instante agregado por geração. Só aparecem as gerações que já
    # ingressaram, então a série de uma geração começa no período do seu
    # ingresso — e o aluno fica na mesma geração do início ao fim, que é o que
    # torna essa leitura mais estável que a idade.
    by_cohort: list[GroupSnapshot]
    # E pelos dois eixos de perfil, na ordem em que o cenário os declara. Os
    # três recortes particionam a mesma população de formas diferentes: somar
    # qualquer um deles reproduz `overall`, e é por isso que dá para trocar de
    # eixo sem trocar de gráfico.
    by_aptitude: list[GroupSnapshot]
    by_affinity: list[GroupSnapshot]
    # Preço das disciplinas no instante. `None` quando nenhuma estava no
    # mercado — sem oferta não há preço, e 0 ali se leria como "de graça".
    prices: PriceStats | None


@dataclass(frozen=True)
class DisciplineSnapshot:
    name: str
    # Período da disciplina na grade, induzido dos pré-requisitos: 1 quando não
    # tem nenhum, senão o maior período entre eles mais um.
    curriculum_period: int
    hours: int  # w_x — repetido aqui para o recorte por carga horária
    seats: int  # q_x no início do período
    filled: int  # vagas preenchidas no período, contando as garantidas
    # Vagas entregues à matrícula garantida dos ingressantes, antes do leilão.
    # Só é diferente de zero nas disciplinas de 1º período — e é o que explica
    # uma disciplina chegar à primeira rodada já quase cheia.
    granted: int
    # Quantos alunos pediram a disciplina no período — deram lance em alguma
    # rodada, ou a receberam na matrícula garantida. Dividido por `seats` dá a
    # concorrência da disciplina, que é a forma de ler a pressão sobre ela.
    requests: int
    # Média de pi_x entre as rodadas em que a disciplina ainda tinha vaga.
    # `None` quando ela nunca esteve no mercado (q_x = 0, ou esgotada pelos
    # ingressantes antes da primeira rodada).
    mean_price: float | None
    approvals: int  # aprovações ao fim do período


@dataclass(frozen=True)
class PeriodReport:
    period: int
    rounds: list[RoundReport]
    aggregate: RoundReport
    disciplines: list[DisciplineSnapshot]
    graduated_now: int  # concluintes neste período


@dataclass(frozen=True)
class RequestRecord:
    """O que aconteceu com uma disciplina que o aluno quis num período.

    Registra toda disciplina com utilidade positiva (eq. 41), inclusive as em
    que o aluno nem chegou a dar lance — `bids` todo zero significa que ela
    saiu de B_a^(t,r) antes (sem vaga, sem carga horária ou sem orçamento), e é
    justamente o caso que costuma explicar um resultado inesperado.
    """

    discipline: str
    utility: float  # u_{a,x}^(t) — eq. (41)
    bids: list[int]  # c_{a,x}^(t,r) por rodada; 0 = não pediu naquela rodada
    # Rodada em que obteve a vaga; `None` = recusada. `GUARANTEED_ROUND` (0) é a
    # matrícula garantida do ingressante, que não passou por rodada nenhuma.
    won_round: int | None
    paid: int  # créditos efetivamente consumidos — eq. (27)
    attempt: int | None  # tentativa (1 = primeira vez cursando)
    grade: float | None  # n_{a,x} obtida ao fim do período — eq. (33)
    approved: bool
    returned: int  # gamma_{a,x}^(t) — créditos devolvidos por ela, eq. (34)


@dataclass(frozen=True)
class StudentPeriodRecord:
    """A linha do histórico de um aluno num período letivo."""

    period: int
    credits_start: int  # C_a^(t,1) — eq. (37)/(36)
    credits_spent: int
    credits_returned: int  # soma de gamma_{a,x}^(t) — eq. (35), sem o Gamma_min
    credits_end: int  # já com Gamma_a^(t) somado — eq. (36)
    satisfaction: float  # psi_a^(t) — eq. (51)
    grade_average: float  # N_a no início do período — eq. (49)
    approved_hours: int  # acumulado ao fim do período
    enrolled_hours: int  # carga horária obtida neste período
    requests: list[RequestRecord]
    graduated: bool  # concluiu o curso neste período — eq. (40)


@dataclass(frozen=True)
class StudentHistory:
    """Histórico período a período de um aluno. Só os períodos em que ele
    participou da matrícula: quem já se formou, ou quem não tem mais nenhuma
    disciplina elegível, simplesmente não aparece dali em diante."""

    student_id: str
    periods: list[StudentPeriodRecord]


@dataclass(frozen=True)
class StudentSummary:
    id: str
    name: str
    entry_period: int  # t_a — eq. (31)
    aptitude: str  # nome do perfil de aptidão
    affinity: str  # nome do perfil de afinidade
    grade_average: float  # N_a — eq. (49)
    approved_hours: int
    hours_to_graduate: int  # S — a carga da grade inteira, igual para todos
    credits: int
    enrollments: int
    approvals: int
    mean_satisfaction: float  # média de psi_a^(t,*) nos períodos cursados
    graduated_at: int | None


@dataclass(frozen=True)
class SimulationResult:
    periods: list[PeriodReport] = field(default_factory=list)
    students: list[StudentSummary] = field(default_factory=list)
    histories: list[StudentHistory] = field(default_factory=list)
    disciplines: list[str] = field(default_factory=list)
    # Período de cada disciplina na grade, induzido dos pré-requisitos.
    curriculum_periods: dict[str, int] = field(default_factory=dict)
    # Os perfis do cenário, na ordem em que `by_aptitude` e `by_affinity` saem.
    aptitude_profiles: list[str] = field(default_factory=list)
    affinity_profiles: list[str] = field(default_factory=list)


def _price_stats(prices: list[int] | list[float]) -> PriceStats | None:
    """Mínimo, média e máximo de pi_x entre as disciplinas no mercado.

    Sem disciplina no mercado não há preço: `None`, e o ponto some do gráfico em
    vez de virar zero.
    """
    if not prices:
        return None
    return PriceStats(min=min(prices), mean=sum(prices) / len(prices), max=max(prices))


def _snapshot_group(
    *,
    group: str | None,
    members: list[Student],
    measured: list[Student],
    satisfactions: dict[str, float],
    grade_averages: dict[str, float],
    semestralizations: dict[str, float],
    scarcities: dict[str, float],
    contentions: dict[str, float],
    approved_hours: dict[str, int],
    won: dict[str, set[str]],
    total_seats: int,
    population: int,
    graduated: int,
    credits: dict[str, int],
    supply: dict[str, int],
    bids: dict[str, int],
    credit_returns: dict[str, int] | None,
    uses_credits: bool,
) -> GroupSnapshot:
    """Um recorte qualquer de alunos: a universidade inteira, uma geração ou um
    perfil.

    `members` é quem está matriculado — a contagem de pessoas. `measured` é o
    subconjunto que de fato disputou: os mesmos, menos os calouros do período,
    pelo motivo explicado em `GroupSnapshot`. Toda média sai de `measured`, e só
    `active` sai de `members`; com `measured` vazio o recorte publica a
    contagem e nenhuma média.

    Sem crédito no cenário (linha de base por CR) as cinco grandezas de crédito
    saem `None`, como já saem num recorte vazio: ali não houve ninguém, aqui não
    há moeda. Zero nos dois casos se leria como um fato — "ninguém gastou" — em
    vez da ausência que é.
    """
    if not measured:
        return GroupSnapshot(
            group=group,
            metrics=None,
            active=len(members),
            population=population,
            graduated=graduated,
            mean_credits=None,
            mean_approved_hours=None,
            credits_per_student=None,
            credits_per_seat=None,
            mean_bids=None,
            mean_credit_return=None,
        )
    group_supply = sum(supply[s.id] for s in measured)
    return GroupSnapshot(
        group=group,
        metrics=compute_metrics(
            satisfactions=[satisfactions[s.id] for s in measured],
            grade_averages=[grade_averages[s.id] for s in measured],
            semestralizations=[semestralizations[s.id] for s in measured],
            scarcities=[scarcities[s.id] for s in measured],
            contentions=[contentions[s.id] for s in measured],
            allocated=sum(len(won[s.id]) for s in measured),
            total_seats=total_seats,
        ),
        active=len(members),
        population=population,
        graduated=graduated,
        mean_credits=(
            sum(credits[s.id] for s in measured) / len(measured) if uses_credits else None
        ),
        mean_approved_hours=sum(approved_hours[s.id] for s in measured) / len(measured),
        credits_per_student=group_supply / len(measured) if uses_credits else None,
        credits_per_seat=(
            group_supply / total_seats if uses_credits and total_seats else None
        ),
        mean_bids=(
            sum(bids[s.id] for s in measured) / len(measured) if uses_credits else None
        ),
        mean_credit_return=(
            sum(credit_returns[s.id] for s in measured) / len(measured)
            if uses_credits and credit_returns is not None
            else None
        ),
    )


def _snapshot_groups(
    *,
    config: SimulationConfig,
    active: list[Student],
    students: list[Student],
    period: int,
    axes: list[_Axis],
    satisfactions: dict[str, float],
    grade_averages: dict[str, float],
    scarcities: dict[str, float],
    contentions: dict[str, float],
    won: dict[str, set[str]],
    total_seats: int,
    credits: dict[str, int],
    supply: dict[str, int],
    bids: dict[str, int],
    ages: dict[str, int],
    hours: dict[str, int],
    credit_returns: dict[str, int] | None = None,
) -> tuple[GroupSnapshot, list[list[GroupSnapshot]]]:
    """O agregado da universidade e um recorte por eixo, no mesmo instante.

    A contagem de concluintes sai de varrer `students`, não de um livro-caixa
    mantido à parte: `graduated_at` só é preenchido ao fim do período, então uma
    varredura durante as rodadas de t dá exatamente "quem já se formou antes de
    t", e a mesma varredura depois delas dá "quem já se formou contando t". É a
    diferença que os dois instantes precisam, de graça — e sem um livro por eixo
    que pudesse divergir do estado real.
    """
    approved_hours = {s.id: s.approved_hours(hours, config.min_grade) for s in active}
    # A idade vem do chamador porque ela acompanha o instante do recorte: nas
    # rodadas de t o aluno completou t - t_a períodos, ao fim de t completou um
    # a mais — e é esse intervalo que `approved_hours` acabou de cobrir.
    # W_a é do perfil de afinidade do aluno, então a semestralização mede cada
    # um contra o que *ele* poderia ter cursado — comparar todos com o mesmo
    # teto penalizaria quem carrega menos por período.
    semestralizations = {
        s.id: semestralization(
            approved_hours=approved_hours[s.id],
            max_hours=s.affinity.max_hours,
            periods_completed=ages[s.id],
        )
        for s in active
    }

    def snapshot(
        *,
        group: str | None,
        members: list[Student],
        population: int,
        graduated: int,
    ) -> GroupSnapshot:
        return _snapshot_group(
            group=group,
            members=members,
            # O calouro do período sai de toda média: ele não disputou nada, e
            # pontua psi = 1 contra CR = 0 por construção (ver `GroupSnapshot`).
            measured=[s for s in members if s.entry_period != period],
            population=population,
            graduated=graduated,
            uses_credits=config.uses_credits,
            satisfactions=satisfactions,
            grade_averages=grade_averages,
            semestralizations=semestralizations,
            scarcities=scarcities,
            contentions=contentions,
            approved_hours=approved_hours,
            won=won,
            total_seats=total_seats,
            credits=credits,
            supply=supply,
            bids=bids,
            credit_returns=credit_returns,
        )

    entered = [s for s in students if s.entry_period <= period]
    overall = snapshot(
        group=None,
        members=active,
        population=len(entered),
        graduated=sum(1 for s in entered if s.graduated_at is not None),
    )

    # Todo grupo do eixo aparece em todo período, tenha ou não aluno ativo:
    # senão a série dele sumiria justamente quando termina de contar por onde
    # cada um saiu. Vale sobretudo na fase de drenagem, em que toda geração
    # acaba esvaziando.
    by_axis: list[list[GroupSnapshot]] = []
    for axis in axes:
        members: dict[str, list[Student]] = {key: [] for key in axis.order}
        for student in active:
            members[axis.key(student)].append(student)
        population = Counter(axis.key(s) for s in entered)
        graduated = Counter(axis.key(s) for s in entered if s.graduated_at is not None)
        by_axis.append(
            [
                snapshot(
                    group=key,
                    members=members[key],
                    population=population[key],
                    graduated=graduated[key],
                )
                for key in axis.order
            ]
        )
    return overall, by_axis


def run_simulation(config: SimulationConfig) -> SimulationResult:
    """Roda a simulação inteira. Determinística: mesma config, mesmo resultado."""
    rng = np.random.default_rng(config.seed)
    uses_credits = config.uses_credits
    students = generate_students(config, rng)
    hours = config.hours_by_discipline()
    total_seats = sum(d.seats for d in config.disciplines)
    curriculum = config.curriculum_periods()
    # As disciplinas sem pré-requisito: a matrícula garantida de quem ingressa.
    first_period = config.first_period_disciplines()
    # Conclusão (eq. 40): toda disciplina é obrigatória, então concluir é
    # aprovar na grade inteira — não há mais carga horária mínima a somar.
    curriculum_set = {d.name for d in config.disciplines}
    hours_to_graduate = config.hours_to_graduate()

    base_grades = initial_grades(students, config.disciplines, rng)
    # u^(t) inteira, sorteada aqui e não dentro do loop: é parâmetro de
    # entrada, como as notas. Ver `behavior.draw_utilities`.
    utility_draws = draw_utilities(students, config, rng)

    # alpha: uma ordem de desempate por disciplina — eq. (20). Fixa para toda a
    # simulação, como exige a Seção 7.1.2.
    student_ids = [s.id for s in students]
    tie_break_order = {
        discipline.name: [student_ids[i] for i in rng.permutation(len(students))]
        for discipline in config.disciplines
    }
    # epsilon: idem — sorteada uma vez para todos os pares (a, x).
    epsilon = stochastic_perturbations(
        [(s.id, d.name) for s in students for d in config.disciplines],
        num_agents=max(len(students), 1),
        num_goods=max(len(config.disciplines), 1),
        seed=config.seed,
    )

    satisfaction_history: dict[str, list[float]] = {s.id: [] for s in students}
    history: dict[str, list[StudentPeriodRecord]] = {s.id: [] for s in students}
    enrollments: dict[str, int] = {s.id: 0 for s in students}
    # Os dois eixos de perfil são fixos: a ordem das séries é a ordem em que o
    # cenário declara os perfis, e todo perfil aparece em todo período, mesmo
    # sem aluno ativo. O eixo das gerações muda de período para período — uma
    # geração só entra na lista depois do seu t_a — e é montado lá dentro.
    aptitude_axis = _Axis(
        key=lambda s: s.aptitude.name, order=[p.name for p in config.aptitude_profiles]
    )
    affinity_axis = _Axis(
        key=lambda s: s.affinity.name, order=[p.name for p in config.affinity_profiles]
    )
    entry_periods = sorted({s.entry_period for s in students})
    periods: list[PeriodReport] = []

    # Invariante dos relatórios: todo período publicado tem pelo menos um aluno
    # ativo, e a numeração vai de 1 a len(periods) sem buraco. Vale porque os
    # ingressos ocorrem em períodos consecutivos a partir do primeiro e, passado o
    # último ingresso (L = `config.entry_span`), a população só diminui — então o
    # primeiro período vazio, se houver, só é seguido de períodos vazios. A
    # simulação para ali: um período sem ninguém não produz métrica nenhuma, só
    # zeros enganosos. Com L < |T| essa parada é o fim natural da drenagem.
    for period in range(1, config.periods + 1):
        # Matriculados: já ingressaram (t_a, eq. 31) e ainda não concluíram.
        enrolled = [
            s for s in students if s.entry_period <= period and s.graduated_at is None
        ]
        if not enrolled:
            break
        active = enrolled

        # Os três eixos de recorte do período. As gerações que já ingressaram
        # entram na ordem em que entraram — a série de uma geração começa no
        # período do seu t_a e não some mais; os perfis são fixos.
        axes = [
            _Axis(
                key=lambda s: str(s.entry_period),
                order=[str(entry) for entry in entry_periods if entry <= period],
            ),
            aptitude_axis,
            affinity_axis,
        ]

        utilities = {
            s.id: utility_matrix(draw=utility_draws[(s.id, period)], student=s, config=config)
            for s in active
        }
        # U_a^(t) — eq. (42), a soma das utilidades do conjunto elegível.
        #
        # O filtro abaixo deixou de ter caso: com a utilidade zerada fora do
        # elegível, U_a só é zero quando nada é elegível, e nada é elegível só
        # para quem aprovou a grade inteira — que já saiu por `graduated_at` e
        # nem chega aqui. (A disciplina não aprovada de menor período tem todos
        # os pré-requisitos aprovados por minimalidade, então sempre há ao menos
        # uma elegível.) Fica como guarda: sem ela, uma grade degenerada
        # dividiria por zero no lugar de simplesmente não publicar o período.
        spend_fraction = {s.id: sum(utilities[s.id].values()) for s in active}
        active = [s for s in active if spend_fraction[s.id] > 0]
        if not active:
            break

        grade_averages = {s.id: s.grade_average(hours) for s in active}
        # q_x^(t,1), a oferta do início do período. `seats` é decrementado a
        # cada vaga preenchida (eq. 13); `config_seats` é a oferta original, que
        # é sobre o que escassez e concorrência se medem.
        config_seats = {d.name: d.seats for d in config.disciplines}
        seats = dict(config_seats)
        # Escassez: elegíveis por vaga, na média das disciplinas que o aluno
        # ainda pode cursar. Medida sobre a oferta do início do período e sobre
        # o conjunto elegível, os dois fixos de r=1 ao fim de t — ela não anda
        # entre as rodadas de propósito, porque descreve o cenário que o aluno
        # encontrou, não o que o leilão fez com ele.
        # e_x: quantos alunos ativos são elegíveis a cada disciplina. Conta toda
        # a universidade, como o n_x da concorrência.
        eligible = {s.id: [n for n in utilities[s.id] if config_seats[n] > 0] for s in active}
        eligible_count: dict[str, int] = {}
        for student in active:
            for name in eligible[student.id]:
                eligible_count[name] = eligible_count.get(name, 0) + 1
        scarcities = {
            s.id: demand_per_seat(
                demands=[eligible_count[n] / config_seats[n] for n in eligible[s.id]]
            )
            for s in active
        }
        capacity = {s.id: float(s.affinity.max_hours) for s in active}  # W_a^(t,1)
        budget = {s.id: s.credits for s in active}  # C_a^(t,1)
        won: dict[str, set[str]] = {s.id: set() for s in active}
        paid: dict[tuple[str, str], int] = {}
        spent: dict[str, int] = {s.id: 0 for s in active}
        price_sum: dict[str, int] = {d.name: 0 for d in config.disciplines}
        # Rodadas em que a disciplina ainda tinha vaga. É o denominador do preço
        # médio dela: uma disciplina esgotada na rodada 1 não recebe mais lance
        # nenhum e cairia no piso da eq. (24) até o fim do período, o que leria
        # como "barata" justamente na que todo mundo quis.
        price_rounds: dict[str, int] = {d.name: 0 for d in config.disciplines}
        # Rastro do período para o histórico individual (tela de depuração).
        credits_start = {s.id: s.credits for s in active}
        # O que o aluno pediu em cada rodada. No leilão guarda c_{a,x}^(t,r), os
        # créditos do lance; na ordenação por CR não há lance, e guarda 1 onde
        # houve solicitação — é o marcador que a concorrência do período lê
        # (`requested`), e que o histórico individual mostra como pedido.
        bid_log: dict[str, dict[str, list[int]]] = {s.id: {} for s in active}
        # Créditos apostados no período, somando as rodadas. Acumula como o
        # gasto, para que as duas séries do mesmo gráfico falem do mesmo
        # intervalo; a diferença entre elas é o que foi apostado e não consumido
        # — lance perdedor, ou o desconto de pagar o preço no lugar do lance.
        bid_total: dict[str, int] = {s.id: 0 for s in active}
        won_round: dict[tuple[str, str], int] = {}

        # Matrícula garantida: quem ingressa neste período entra direto em todas
        # as disciplinas de 1º período, antes de o leilão abrir. Não dá lance —
        # o sistema reparte o orçamento dele igualmente entre elas e lança o
        # gasto, ficando com o resto da divisão no saldo. É esse valor que o
        # retorno de créditos (eq. 34) tem para trabalhar. A validação do
        # cenário garante que a geração cabe na menor dessas ofertas e que a
        # carga somada respeita W_a (eq. 4).
        granted: dict[str, int] = {d.name: 0 for d in config.disciplines}
        guaranteed: dict[str, list[str]] = {s.id: [] for s in active}
        for student in (s for s in active if s.entry_period == period):
            # Sem crédito não há o que lançar na conta: a vaga garantida é a
            # mesma nos dois mecanismos, e o que muda é só se ela custa algo.
            share = budget[student.id] // len(first_period) if uses_credits else 0
            marker = share if uses_credits else 1
            for name in first_period:
                guaranteed[student.id].append(name)
                won[student.id].add(name)
                won_round[(student.id, name)] = GUARANTEED_ROUND
                seats[name] -= 1  # eq. (13)
                granted[name] += 1
                capacity[student.id] -= hours[name]  # eq. (14)
                budget[student.id] -= share  # eq. (27)
                spent[student.id] += share
                paid[(student.id, name)] = share
                bid_log[student.id].setdefault(name, [0] * config.rounds)[0] = marker
                bid_total[student.id] += share

        # As rodadas guardam só o que muda nelas; o relatório de cada uma é
        # montado depois do laço, quando a concorrência do período (que depende
        # dos lances de *todas* as rodadas) já existe. O saldo de créditos entra
        # copiado porque `budget` continua sendo descontado rodada a rodada.
        round_states: list[_RoundState] = []
        for round_number in range(1, config.rounds + 1):
            # Quem está no mercado nesta rodada, antes de a alocação consumir
            # vaga: só essas disciplinas têm preço com leitura. As vagas já
            # entregues aos ingressantes saíram do mercado antes da rodada 1.
            offered = [d.name for d in config.disciplines if seats[d.name] > 0]
            # B_a^(t,r): disciplinas em que ainda é possível obter vaga — há
            # vaga livre, cabe na carga horária restante e o aluno ainda não a
            # conquistou neste período (eq. 15). O ingressante já conquistou
            # tudo que lhe é elegível, então sai daqui vazio e não pede nada.
            # O conjunto é o mesmo nos dois mecanismos: o que muda é o que o
            # aluno faz com ele — repartir créditos ou escolher quais pedir.
            available = {
                s.id: [
                    name
                    for name in utilities[s.id]
                    if seats[name] > 0
                    and hours[name] <= capacity[s.id]
                    and name not in won[s.id]
                ]
                for s in active
            }
            # A vaga garantida entra como conquista da rodada 1: é ali que ela
            # passa a valer, e sem isso o ingressante apareceria com satisfação
            # zero na primeira rodada e plena só no agregado do período.
            won_now: dict[str, list[str]] = {
                s.id: list(guaranteed[s.id]) if round_number == 1 else [] for s in active
            }
            # `None` fora do leilão: sem lance não se forma preço, e a série
            # some do gráfico em vez de virar uma linha de piso que ninguém
            # pagou.
            round_prices: dict[str, int] | None = None

            if uses_credits:
                bids: list[Bid] = []
                for student in active:
                    student_bids = compute_bids(
                        utilities=utilities[student.id],
                        available=available[student.id],
                        budget=budget[student.id],
                        spend_fraction=spend_fraction[student.id],
                    )
                    for name, credits in student_bids.items():
                        bid_log[student.id].setdefault(name, [0] * config.rounds)[
                            round_number - 1
                        ] = credits
                    bid_total[student.id] += sum(student_bids.values())
                    bids.extend(
                        Bid(student.id, name, credits)
                        for name, credits in student_bids.items()
                    )

                # pi_x da rodada — eq. (24). O piso de 1 crédito é o valor da
                # equação quando não houve lance mal-sucedido, inclusive quando
                # não houve lance nenhum e o leilão nem chegou a rodar.
                round_prices = {name: 1 for name in offered}
                if bids:
                    result = run_auction(
                        AuctionInput(
                            agents=[Agent(s.id, capacity[s.id]) for s in active],
                            goods=[
                                Good(d.name, seats[d.name], d.hours)
                                for d in config.disciplines
                            ],
                            budgets=budget,
                            bids=bids,
                            tie_break_order=tie_break_order,
                            epsilon=epsilon,
                            seed=config.seed,
                        )
                    )
                    for (student_id, name), allocated in result.allocation.items():
                        if allocated:
                            won_now[student_id].append(name)
                            won[student_id].add(name)
                            won_round[(student_id, name)] = round_number
                            seats[name] -= 1  # eq. (13)
                            capacity[student_id] -= hours[name]  # eq. (14)
                    for (student_id, name), consumed in result.consumption.items():
                        budget[student_id] -= consumed  # eq. (27)
                        spent[student_id] += consumed
                        paid[(student_id, name)] = (
                            paid.get((student_id, name), 0) + consumed
                        )
                    for name, price in result.prices.items():
                        if name in round_prices:
                            round_prices[name] = price
            else:
                # Linha de base: o aluno resolve a carga horária em casa
                # (eq. 50) e a universidade atende por ordem de CR (eq. 49).
                # Não há lance, orçamento nem preço — e, como cada pedido já
                # cabe no que resta de W_a, atender todos os de um aluno é
                # viável por construção e a varredura não reverifica nada.
                requests: list[tuple[str, str]] = []
                for student in active:
                    for name in request_set(
                        utilities=utilities[student.id],
                        available=available[student.id],
                        hours=hours,
                        capacity=int(capacity[student.id]),
                        spend_fraction=spend_fraction[student.id],
                    ):
                        bid_log[student.id].setdefault(name, [0] * config.rounds)[
                            round_number - 1
                        ] = 1
                        requests.append((student.id, name))
                # A prioridade é do **aluno**, não do par: o mesmo CR vale em
                # todas as disciplinas que ele pediu. O epsilon só desempata.
                priority = {
                    key: grade_averages[key[0]] + epsilon.get(key, 0.0) for key in requests
                }
                for student_id, name in allocate_by_ranking(
                    requests=requests, priority=priority, seats=seats
                ):
                    won_now[student_id].append(name)
                    won[student_id].add(name)
                    won_round[(student_id, name)] = round_number
                    seats[name] -= 1  # eq. (13)
                    capacity[student_id] -= hours[name]  # eq. (14)

            round_satisfaction = {
                s.id: satisfaction(
                    utilities=utilities[s.id],
                    spend_fraction=spend_fraction[s.id],
                    allocated=won_now[s.id],
                )
                for s in active
            }
            if round_prices is not None:
                for name, price in round_prices.items():
                    price_sum[name] += price
                    price_rounds[name] += 1

            round_states.append(
                _RoundState(
                    number=round_number,
                    satisfaction=round_satisfaction,
                    won={s.id: set(won_now[s.id]) for s in active},
                    budget=dict(budget),
                    bids=dict(bid_total),
                    prices=(
                        _price_stats(list(round_prices.values()))
                        if round_prices is not None
                        else None
                    ),
                )
            )

        # Concorrência: candidatos por vaga nas disciplinas que o aluno de
        # fato pediu — aquelas em que deu lance (ou, na linha de base, fez
        # solicitação) em alguma rodada; `bid_log` guarda zero nas rodadas em
        # que não pediu. A matrícula garantida conta
        # como pedido: o ingressante não disputou, mas ocupa a vaga, e para quem
        # recursa a disciplina a pressão é a mesma. Como a escassez, é do
        # período inteiro e usa a oferta do início dele, então também não anda
        # entre as rodadas.
        requested = {
            s.id: {name for name, log in bid_log[s.id].items() if any(log)}
            | set(guaranteed[s.id])
            for s in active
        }
        # n_x: quantos pediram cada disciplina. Conta toda a universidade.
        demand: dict[str, int] = {}
        for student in active:
            for name in requested[student.id]:
                demand[name] = demand.get(name, 0) + 1
        contentions = {
            s.id: demand_per_seat(
                # Uma disciplina sem vaga nunca entra em B_a^(t,r), então quem
                # está aqui tem q_x >= 1.
                demands=[demand[name] / config_seats[name] for name in requested[s.id]]
            )
            for s in active
        }

        round_reports: list[RoundReport] = []
        for state in round_states:
            overall, (by_cohort, by_aptitude, by_affinity) = _snapshot_groups(
                config=config,
                active=active,
                students=students,
                period=period,
                axes=axes,
                satisfactions=state.satisfaction,
                grade_averages=grade_averages,
                scarcities=scarcities,
                contentions=contentions,
                won=state.won,
                total_seats=total_seats,
                credits=state.budget,
                supply=credits_start,
                bids=state.bids,
                # Em plena rodada de t, o aluno completou t - t_a períodos: o
                # que ele cursa agora ainda não foi avaliado.
                ages={s.id: period - s.entry_period for s in active},
                hours=hours,
            )
            round_reports.append(
                RoundReport(
                    period=period,
                    round=state.number,
                    overall=overall,
                    by_cohort=by_cohort,
                    by_aptitude=by_aptitude,
                    by_affinity=by_affinity,
                    prices=state.prices,
                )
            )

        # Fim do período: notas (eq. 33), retorno de créditos (eqs. 34-36) e
        # conclusão de curso (eq. 40).
        approvals: dict[str, int] = {d.name: 0 for d in config.disciplines}
        attempt_log: dict[tuple[str, str], tuple[int, float]] = {}
        # gamma_{a,x}^(t) por disciplina (para o histórico) e sua soma por aluno
        # (para o recorte por geração).
        returned_by_discipline: dict[tuple[str, str], int] = {}
        credits_returned: dict[str, int] = {}
        graduated_now = 0
        for student in active:
            enrollments[student.id] += len(won[student.id])
            returned = 0
            for name in won[student.id]:
                attempt = student.attempts.get(name, 0) + 1
                student.attempts[name] = attempt
                grade = grade_for_attempt(
                    base_grades[(student.id, name)], attempt, student.aptitude.learning_gain
                )
                student.grades[name] = max(student.grades.get(name, 0.0), grade)
                attempt_log[(student.id, name)] = (attempt, student.grades[name])
                if student.grades[name] >= config.min_grade:
                    approvals[name] += 1
                # f_gamma (eq. 34) é do leilão: devolve parte do *preço pago*.
                # Na linha de base por CR não houve preço nem pagamento, então
                # não há o que devolver, qualquer que seja a política escolhida.
                gamma = (
                    credit_return(
                        config.credit_return,
                        paid=paid.get((student.id, name), 0),
                        grade=student.grades[name],
                        min_grade=config.min_grade,
                    )
                    if uses_credits
                    else 0
                )
                returned_by_discipline[(student.id, name)] = gamma
                returned += gamma
            credits_returned[student.id] = returned
            # eq. (36): o que sobrou do período é carregado e soma-se ao
            # retorno total Gamma_a^(t) = Gamma_min + soma gamma_{a,x} (eq. 35).
            # Fora do leilão o saldo não se move — nada foi gasto, e inflá-lo
            # com Gamma_min a cada período daria um número sem significado.
            if uses_credits:
                student.credits = (
                    student.credits - spent[student.id] + config.base_credits + returned
                )

            # Conclusão — eq. (40): toda disciplina é obrigatória, então conclui
            # quem aprovou na grade inteira.
            if curriculum_set <= student.approved(config.min_grade):
                student.graduated_at = period
                graduated_now += 1

        period_satisfaction = {
            s.id: satisfaction(
                utilities=utilities[s.id],
                spend_fraction=spend_fraction[s.id],
                allocated=sorted(won[s.id]),
            )
            for s in active
        }
        for student in active:
            satisfaction_history[student.id].append(period_satisfaction[student.id])
            requests = []
            for name, utility in sorted(
                utilities[student.id].items(), key=lambda item: -item[1]
            ):
                attempt = attempt_log.get((student.id, name))
                requests.append(
                    RequestRecord(
                        discipline=name,
                        utility=utility,
                        bids=bid_log[student.id].get(name, [0] * config.rounds),
                        won_round=won_round.get((student.id, name)),
                        paid=paid.get((student.id, name), 0),
                        attempt=attempt[0] if attempt else None,
                        grade=attempt[1] if attempt else None,
                        approved=bool(attempt and attempt[1] >= config.min_grade),
                        returned=returned_by_discipline.get((student.id, name), 0),
                    )
                )
            history[student.id].append(
                StudentPeriodRecord(
                    period=period,
                    credits_start=credits_start[student.id],
                    credits_spent=spent[student.id],
                    credits_returned=credits_returned[student.id],
                    credits_end=student.credits,
                    satisfaction=period_satisfaction[student.id],
                    grade_average=grade_averages[student.id],
                    approved_hours=student.approved_hours(hours, config.min_grade),
                    enrolled_hours=sum(hours[name] for name in won[student.id]),
                    requests=requests,
                    graduated=student.graduated_at == period,
                )
            )

        # `grade_averages` é o CR vigente no início do período — o que estava
        # valendo durante os leilões. As notas deste período só entram no CR do
        # período seguinte, como acontece numa matrícula de verdade.
        overall, (by_cohort, by_aptitude, by_affinity) = _snapshot_groups(
            config=config,
            active=active,
            students=students,
            period=period,
            axes=axes,
            satisfactions=period_satisfaction,
            grade_averages=grade_averages,
            scarcities=scarcities,
            contentions=contentions,
            won=won,
            total_seats=total_seats,
            credits=budget,
            supply=credits_start,
            bids=bid_total,
            # Aqui as notas de t já saíram: o período conta como completo.
            ages={s.id: period - s.entry_period + 1 for s in active},
            hours=hours,
            credit_returns=credits_returned,
        )
        # O preço do período de uma disciplina é a média das rodadas em que ela
        # esteve no mercado; a faixa do período é a dispersão desses valores.
        period_prices = {
            d.name: price_sum[d.name] / price_rounds[d.name]
            for d in config.disciplines
            if price_rounds[d.name]
        }
        periods.append(
            PeriodReport(
                period=period,
                rounds=round_reports,
                aggregate=RoundReport(
                    period=period,
                    round=0,
                    overall=overall,
                    by_cohort=by_cohort,
                    by_aptitude=by_aptitude,
                    by_affinity=by_affinity,
                    prices=_price_stats(list(period_prices.values())),
                ),
                disciplines=[
                    DisciplineSnapshot(
                        name=d.name,
                        curriculum_period=curriculum[d.name],
                        hours=d.hours,
                        seats=d.seats,
                        filled=d.seats - seats[d.name],
                        granted=granted[d.name],
                        requests=demand.get(d.name, 0),
                        mean_price=period_prices.get(d.name),
                        approvals=approvals[d.name],
                    )
                    for d in config.disciplines
                ],
                graduated_now=graduated_now,
            )
        )

    return SimulationResult(
        periods=periods,
        students=[
            StudentSummary(
                id=s.id,
                name=s.name,
                entry_period=s.entry_period,
                aptitude=s.aptitude.name,
                affinity=s.affinity.name,
                grade_average=s.grade_average(hours),
                approved_hours=s.approved_hours(hours, config.min_grade),
                hours_to_graduate=hours_to_graduate,
                credits=s.credits,
                enrollments=enrollments[s.id],
                approvals=len(s.approved(config.min_grade)),
                mean_satisfaction=(
                    sum(satisfaction_history[s.id]) / len(satisfaction_history[s.id])
                    if satisfaction_history[s.id]
                    else 0.0
                ),
                graduated_at=s.graduated_at,
            )
            for s in students
        ],
        histories=[
            StudentHistory(student_id=s.id, periods=history[s.id]) for s in students
        ],
        disciplines=[d.name for d in config.disciplines],
        curriculum_periods=curriculum,
        aptitude_profiles=[p.name for p in config.aptitude_profiles],
        affinity_profiles=[p.name for p in config.affinity_profiles],
    )
