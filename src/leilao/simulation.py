"""Simulação multi-período da matrícula universitária (Seção 7.2).

Amarra as peças: a cada período letivo t sorteia-se a matriz de utilidades dos
alunos ativos, roda-se |R| rodadas de leilão (motor da Seção 7.1, reaproveitado
tal e qual), e ao fim do período saem as notas, o retorno de créditos e as
conclusões de curso.

    para cada período t:
        u^(t)                                      eqs. (41)-(43), (47)-(48)
        para cada rodada r:
            c^(t,r) <- u^(t), C^(t,r), B_a^(t,r)   eqs. (44)-(46)
            z^(t,r) <- leilão(c^(t,r))             eqs. (22)-(25)
            q, W, C                                eqs. (13), (14), (27)
        notas, retorno de créditos                 eqs. (33)-(36)
        conclusão de curso                         eq. (40)
        jubilamento                                `SimulationConfig.max_residence`

O aluno sai do conjunto ativo por duas portas: concluindo o curso (eq. 40) ou
sendo desligado por decurso de prazo. O jubilamento não está no anteprojeto —
foi acrescentado porque sem ele quem nunca consegue vaga permanece disputando
para sempre, e porque a taxa de desligamento é o que distingue de forma mais
legível um mecanismo que serve mal os mesmos alunos período após período.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .auction import AuctionInput, Bid, run_auction
from .behavior import compute_bids, draw_utilities, utility_matrix
from .config import Course, SimulationConfig
from .entities import Agent, Good
from .grading import credit_return, grade_for_attempt, initial_grades
from .metrics import Metrics, compute_metrics, demand_per_seat, satisfaction, semestralization
from .population import Student, generate_students
from .tie_breaking import stochastic_perturbations


@dataclass(frozen=True)
class CourseSnapshot:
    """Recorte de um curso num instante da simulação — a unidade dos gráficos.

    Quando o curso não tem nenhum aluno no período (`active == 0`), as médias
    são `None` em vez de 0,0: não havia ninguém, o que é diferente de ninguém
    ter ficado satisfeito. Zero ali seria um ponto falso no gráfico e puxaria
    para baixo qualquer média feita sobre os períodos.
    """

    course: str
    # `None` no recorte do curso inteiro (`RoundReport.by_course`); em
    # `RoundReport.by_cohort`, o periodo de ingresso (t_a, eq. 31) da geracao
    # agregada ali -- a geracao e identificada pelo periodo em que entrou. Os dois recortes tem os mesmos campos de proposito: trocar
    # a agregacao de um grafico e trocar de lista, nada mais.
    entry_period: int | None
    metrics: Metrics | None
    active: int  # |A_k^(t)| no início do período
    # Alunos do recorte que já ingressaram, tenham saído ou não. Não é
    # `active + graduated + dismissed`: quem sai ao fim de t conta nos dois
    # lados dessa soma, porque disputou o período inteiro antes de sair. É
    # sobre este número que se tira a fração de formados ou de jubilados.
    population: int
    graduated: int  # concluintes acumulados até aqui
    # Jubilados acumulados até aqui. Junto com `active` e `graduated` fecha a
    # população do recorte que já ingressou, então a fração de jubilados do
    # recorte sai dos três sem precisar do tamanho da geração.
    dismissed: int
    mean_credits: float | None  # orçamento médio C_a ao fim do recorte
    mean_approved_hours: float | None
    # Economia de créditos do curso, medida sobre a oferta do início do período
    # (C_a^(t,1), antes de qualquer lance) — distinta de `mean_credits`, que é
    # o que sobrou. `credits_per_seat` divide essa oferta pelas vagas de toda a
    # universidade: é o preço que uma vaga teria se todo o crédito em mãos
    # fosse gasto, e a soma dos cursos dá o preço esperado global.
    credits_per_student: float | None
    credits_per_seat: float | None
    # Créditos apostados no período por aluno ativo, somando as rodadas. Pode
    # passar do orçamento: lance perdido não consome nada (eq. 25), então o
    # crédito que não virou vaga volta a ser apostado na rodada seguinte.
    mean_bids: float | None
    # Retorno de créditos do período (soma de gamma_{a,x}, eq. 34), por aluno
    # ativo. Só existe no recorte de fim de período: em plena rodada as notas
    # ainda não saíram, e ali o campo vem `None` — não 0,0, que se leria como
    # "a política não devolveu nada".
    mean_credit_return: float | None


@dataclass(frozen=True)
class PriceStats:
    """Dispersão de pi_x (eq. 24) entre as disciplinas num instante.

    O preço não é grandeza de aluno nem de curso: é do mercado. O que se lê dele
    ao longo do tempo é a faixa — a disciplina mais cara, a média e a mais
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
    overall: Metrics
    by_course: list[CourseSnapshot]
    # O mesmo instante agregado por curso x geracao. So aparecem as geracoes
    # que ja ingressaram, entao a serie de uma geracao comeca no periodo do seu
    # ingresso -- e o aluno fica na mesma geracao do inicio ao fim, que e o que
    # torna essa leitura mais estavel que a idade.
    by_cohort: list[CourseSnapshot]
    # Preço das disciplinas no instante. `None` quando nenhuma estava no
    # mercado — sem oferta não há preço, e 0 ali se leria como "de graça".
    prices: PriceStats | None


@dataclass(frozen=True)
class DisciplineSnapshot:
    name: str
    seats: int  # q_x no início do período
    filled: int  # vagas preenchidas no período
    # Média de pi_x entre as rodadas em que a disciplina ainda tinha vaga.
    # `None` quando ela nunca esteve no mercado (q_x = 0).
    mean_price: float | None
    approvals: int  # aprovações ao fim do período


@dataclass(frozen=True)
class PeriodReport:
    period: int
    rounds: list[RoundReport]
    aggregate: RoundReport
    disciplines: list[DisciplineSnapshot]
    graduated_now: int  # concluintes neste período
    dismissed_now: int  # jubilados neste período


@dataclass(frozen=True)
class RequestRecord:
    """O que aconteceu com uma disciplina que o aluno quis num período.

    Registra toda disciplina com utilidade positiva (eq. 41), inclusive as em
    que o aluno nem chegou a dar lance — `bids` todo zero significa que ela
    saiu de B_a^(t,r) antes (sem vaga, sem carga horária ou sem orçamento), e é
    justamente o caso que costuma explicar um resultado inesperado.
    """

    discipline: str
    kind: str  # "required" (M_k), "elective" (O_k) ou "free" (L_k)
    utility: float  # u_{a,x}^(t) — eq. (41)
    bids: list[int]  # c_{a,x}^(t,r) por rodada; 0 = não pediu naquela rodada
    won_round: int | None  # rodada em que obteve a vaga; None = recusada
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
    dismissed: bool  # foi jubilado ao fim deste período


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
    course: str
    entry_period: int  # t_a — eq. (31)
    grade_average: float  # N_a — eq. (49)
    approved_hours: int
    hours_to_graduate: int
    credits: int
    enrollments: int
    approvals: int
    mean_satisfaction: float  # média de psi_a^(t,*) nos períodos cursados
    graduated_at: int | None
    dismissed_at: int | None


@dataclass(frozen=True)
class SimulationResult:
    periods: list[PeriodReport] = field(default_factory=list)
    students: list[StudentSummary] = field(default_factory=list)
    histories: list[StudentHistory] = field(default_factory=list)
    courses: list[str] = field(default_factory=list)
    disciplines: list[str] = field(default_factory=list)


def _curriculum_kind(course: Course, discipline: str) -> str:
    """Em que grupo da grade do curso a disciplina cai — M_k, O_k ou L_k."""
    if discipline in course.required:
        return "required"
    if discipline in course.electives:
        return "elective"
    return "free"


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
    course: str,
    entry_period: int | None,
    members: list[Student],
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
    dismissed: int,
    credits: dict[str, int],
    supply: dict[str, int],
    bids: dict[str, int],
    credit_returns: dict[str, int] | None,
) -> CourseSnapshot:
    """Um recorte qualquer de alunos: um curso inteiro ou uma coorte dele."""
    if not members:
        return CourseSnapshot(
            course=course,
            entry_period=entry_period,
            metrics=None,
            active=0,
            population=population,
            graduated=graduated,
            dismissed=dismissed,
            mean_credits=None,
            mean_approved_hours=None,
            credits_per_student=None,
            credits_per_seat=None,
            mean_bids=None,
            mean_credit_return=None,
        )
    group_supply = sum(supply[s.id] for s in members)
    return CourseSnapshot(
        course=course,
        entry_period=entry_period,
        metrics=compute_metrics(
            satisfactions=[satisfactions[s.id] for s in members],
            grade_averages=[grade_averages[s.id] for s in members],
            semestralizations=[semestralizations[s.id] for s in members],
            scarcities=[scarcities[s.id] for s in members],
            contentions=[contentions[s.id] for s in members],
            allocated=sum(len(won[s.id]) for s in members),
            total_seats=total_seats,
        ),
        active=len(members),
        population=population,
        graduated=graduated,
        dismissed=dismissed,
        mean_credits=sum(credits[s.id] for s in members) / len(members),
        mean_approved_hours=sum(approved_hours[s.id] for s in members) / len(members),
        credits_per_student=group_supply / len(members),
        credits_per_seat=group_supply / total_seats if total_seats else None,
        mean_bids=sum(bids[s.id] for s in members) / len(members),
        mean_credit_return=(
            sum(credit_returns[s.id] for s in members) / len(members)
            if credit_returns is not None
            else None
        ),
    )


def _snapshot_courses(
    *,
    config: SimulationConfig,
    active: list[Student],
    satisfactions: dict[str, float],
    grade_averages: dict[str, float],
    scarcities: dict[str, float],
    contentions: dict[str, float],
    won: dict[str, set[str]],
    total_seats: int,
    entered: dict[tuple[str, int | None], int],
    graduated_so_far: dict[str, int],
    graduated_by_entry: dict[tuple[str, int], int],
    dismissed_so_far: dict[str, int],
    dismissed_by_entry: dict[tuple[str, int], int],
    credits: dict[str, int],
    supply: dict[str, int],
    bids: dict[str, int],
    ages: dict[str, int],
    hours: dict[str, int],
    credit_returns: dict[str, int] | None = None,
) -> tuple[Metrics, list[CourseSnapshot], list[CourseSnapshot]]:
    approved_hours = {s.id: s.approved_hours(hours, config.min_grade) for s in active}
    # A idade vem do chamador porque ela acompanha o instante do recorte: nas
    # rodadas de t o aluno completou t - t_a períodos, ao fim de t completou um
    # a mais — e é esse intervalo que `approved_hours` acabou de cobrir.
    semestralizations = {
        s.id: semestralization(
            approved_hours=approved_hours[s.id],
            max_hours=config.max_hours,
            periods_completed=ages[s.id],
        )
        for s in active
    }

    overall = compute_metrics(
        satisfactions=[satisfactions[s.id] for s in active],
        grade_averages=[grade_averages[s.id] for s in active],
        semestralizations=[semestralizations[s.id] for s in active],
        scarcities=[scarcities[s.id] for s in active],
        contentions=[contentions[s.id] for s in active],
        allocated=sum(len(won[s.id]) for s in active),
        total_seats=total_seats,
    )

    def snapshot(
        *,
        course: str,
        entry_period: int | None,
        members: list[Student],
        graduated: int,
        dismissed: int,
    ) -> CourseSnapshot:
        return _snapshot_group(
            course=course,
            entry_period=entry_period,
            members=members,
            population=entered.get((course, entry_period), 0),
            graduated=graduated,
            dismissed=dismissed,
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

    by_course: list[CourseSnapshot] = []
    by_cohort: list[CourseSnapshot] = []
    for course in config.courses:
        members = [s for s in active if s.course == course.name]
        by_course.append(
            snapshot(
                course=course.name,
                entry_period=None,
                members=members,
                graduated=graduated_so_far.get(course.name, 0),
                dismissed=dismissed_so_far.get(course.name, 0),
            )
        )
        by_entry: dict[int, list[Student]] = {}
        for student in members:
            by_entry.setdefault(student.entry_period, []).append(student)
        # Uma geracao ja sem aluno ativo continua aparecendo enquanto tiver
        # concluintes ou jubilados: senao a serie dela sumiria justamente
        # quando termina de contar por onde cada um saiu. Vale sobretudo na
        # fase de drenagem, em que toda geracao acaba esvaziando.
        left = {
            entry
            for ledger in (graduated_by_entry, dismissed_by_entry)
            for (name, entry) in ledger
            if name == course.name
        }
        for entry in sorted(set(by_entry) | left):
            by_cohort.append(
                snapshot(
                    course=course.name,
                    entry_period=entry,
                    members=by_entry.get(entry, []),
                    graduated=graduated_by_entry.get((course.name, entry), 0),
                    dismissed=dismissed_by_entry.get((course.name, entry), 0),
                )
            )
    return overall, by_course, by_cohort


def run_simulation(config: SimulationConfig) -> SimulationResult:
    """Roda a simulação inteira. Determinística: mesma config, mesmo resultado."""
    rng = np.random.default_rng(config.seed)
    students = generate_students(config, rng)
    course_by_name = {c.name: c for c in config.courses}
    hours = config.hours_by_discipline()
    total_seats = sum(d.seats for d in config.disciplines)

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
    graduated_so_far: dict[str, int] = {course.name: 0 for course in config.courses}
    # Concluintes por (curso, periodo de ingresso) -- quantos da geracao que
    # entrou em t_a ja concluiram, que e o que o recorte por geracao mostra.
    graduated_by_entry: dict[tuple[str, int], int] = {}
    # Mesmos dois livros para a outra porta de saída, o jubilamento.
    dismissed_so_far: dict[str, int] = {course.name: 0 for course in config.courses}
    dismissed_by_entry: dict[tuple[str, int], int] = {}
    # Tamanho de cada geração (fixo) e do curso inteiro (cresce a cada ingresso
    # até L e estaciona). Sai da população de fato, não de
    # `students_per_generation`, para não repetir a regra de geração aqui.
    cohort_size: dict[tuple[str, int], int] = {}
    for student in students:
        key = (student.course, student.entry_period)
        cohort_size[key] = cohort_size.get(key, 0) + 1
    periods: list[PeriodReport] = []

    # Invariante dos relatórios: todo período publicado tem pelo menos um aluno
    # ativo, e a numeração vai de 1 a len(periods) sem buraco. Vale porque as
    # ingressos ocorrem em períodos consecutivos a partir do primeiro e, passado o
    # último ingresso (L = `config.entry_span`), a população só diminui — então o
    # primeiro período vazio, se houver, só é seguido de períodos vazios. A
    # simulação para ali: um período sem ninguém não produz métrica nenhuma, só
    # zeros enganosos. Com L < |T| essa parada é o fim natural da drenagem.
    for period in range(1, config.periods + 1):
        # Matriculados: já ingressaram (t_a, eq. 31) e ainda não saíram, nem
        # concluindo o curso nem jubilados.
        enrolled = [
            s
            for s in students
            if s.entry_period <= period
            and s.graduated_at is None
            and s.dismissed_at is None
        ]
        if not enrolled:
            break
        active = enrolled

        # Quem já ingressou até aqui, por recorte — o denominador das frações
        # de formados e de jubilados. Uma geração só entra depois do seu t_a.
        entered: dict[tuple[str, int | None], int] = {}
        for (course_name, entry), size in cohort_size.items():
            if entry > period:
                continue
            entered[(course_name, entry)] = size
            entered[(course_name, None)] = entered.get((course_name, None), 0) + size

        utilities = {
            s.id: utility_matrix(
                draw=utility_draws[(s.id, period)],
                student=s,
                course=course_by_name[s.course],
                config=config,
            )
            for s in active
        }
        # U_a^(t) — eq. (42). Quem não tem mais nenhuma disciplina elegível não
        # consegue dar lance e fica de fora do período, mas continua matriculado
        # em `enrolled`: o prazo de jubilamento corre para ele também.
        spend_fraction = {s.id: sum(utilities[s.id].values()) for s in active}
        active = [s for s in active if spend_fraction[s.id] > 0]
        # Ninguém pode dar lance: não há leilão nem métrica a publicar, e a
        # simulação acaba aqui. Quem ainda estivesse matriculado fica sem
        # desligamento registrado — é o único caso em que isso acontece, e só
        # ocorre no período degenerado em que a universidade inteira esgotou as
        # disciplinas elegíveis de uma vez.
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
        # a universidade, como o n_x da concorrência: quem disputa uma vaga com
        # o aluno não é só quem está no curso dele.
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
        capacity = {s.id: float(config.max_hours) for s in active}  # W_a^(t,1)
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
        bid_log: dict[str, dict[str, list[int]]] = {s.id: {} for s in active}
        # Créditos apostados no período, somando as rodadas. Acumula como o
        # gasto, para que as duas séries do mesmo gráfico falem do mesmo
        # intervalo; a diferença entre elas é o que foi apostado e não consumido
        # — lance perdedor, ou o desconto de pagar o preço no lugar do lance.
        bid_total: dict[str, int] = {s.id: 0 for s in active}
        won_round: dict[tuple[str, str], int] = {}

        # As rodadas guardam só o que muda nelas; o relatório de cada uma é
        # montado depois do laço, quando a concorrência do período (que depende
        # dos lances de *todas* as rodadas) já existe. O saldo de créditos entra
        # copiado porque `budget` continua sendo descontado rodada a rodada.
        round_states: list[_RoundState] = []
        for round_number in range(1, config.rounds + 1):
            # Quem está no mercado nesta rodada, antes de a alocação consumir
            # vaga: só essas disciplinas têm preço com leitura.
            offered = [d.name for d in config.disciplines if seats[d.name] > 0]
            bids: list[Bid] = []
            for student in active:
                # B_a^(t,r): disciplinas em que ainda é possível obter vaga —
                # há vaga livre, cabe na carga horária restante e o aluno ainda
                # não a conquistou neste período (eq. 15).
                available = [
                    name
                    for name in utilities[student.id]
                    if seats[name] > 0
                    and hours[name] <= capacity[student.id]
                    and name not in won[student.id]
                ]
                student_bids = compute_bids(
                    utilities=utilities[student.id],
                    available=available,
                    budget=budget[student.id],
                    spend_fraction=spend_fraction[student.id],
                )
                for name, credits in student_bids.items():
                    bid_log[student.id].setdefault(name, [0] * config.rounds)[
                        round_number - 1
                    ] = credits
                bid_total[student.id] += sum(student_bids.values())
                bids.extend(Bid(student.id, name, credits) for name, credits in student_bids.items())

            won_now: dict[str, list[str]] = {s.id: [] for s in active}
            # pi_x da rodada — eq. (24). O piso de 1 crédito é o valor da
            # equação quando não houve lance mal-sucedido, inclusive quando não
            # houve lance nenhum e o leilão nem chegou a rodar.
            round_prices: dict[str, int] = {name: 1 for name in offered}
            if bids:
                result = run_auction(
                    AuctionInput(
                        agents=[Agent(s.id, capacity[s.id]) for s in active],
                        goods=[Good(d.name, seats[d.name], d.hours) for d in config.disciplines],
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
                    paid[(student_id, name)] = paid.get((student_id, name), 0) + consumed
                for name, price in result.prices.items():
                    if name in round_prices:
                        round_prices[name] = price

            round_satisfaction = {
                s.id: satisfaction(
                    utilities=utilities[s.id],
                    spend_fraction=spend_fraction[s.id],
                    allocated=won_now[s.id],
                )
                for s in active
            }
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
                    prices=_price_stats(list(round_prices.values())),
                )
            )

        # Concorrência: candidatos por vaga nas disciplinas que o aluno de
        # fato pediu — aquelas em que deu lance em alguma rodada (`bid_log`
        # guarda zero nas rodadas em que não pediu). Como a escassez, é do
        # período inteiro e usa a oferta do início dele, então também não anda
        # entre as rodadas.
        requested = {
            s.id: {name for name, log in bid_log[s.id].items() if any(log)} for s in active
        }
        # n_x: quantos pediram cada disciplina. Conta toda a universidade, não o
        # recorte — a disputa por uma vaga não respeita a fronteira do curso, e
        # é justamente isso que distingue dois cursos que pedem o mesmo bem de
        # dois que pedem bens diferentes.
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
            overall, by_course, by_cohort = _snapshot_courses(
                config=config,
                active=active,
                satisfactions=state.satisfaction,
                grade_averages=grade_averages,
                scarcities=scarcities,
                contentions=contentions,
                won=state.won,
                total_seats=total_seats,
                entered=entered,
                graduated_so_far=graduated_so_far,
                graduated_by_entry=graduated_by_entry,
                dismissed_so_far=dismissed_so_far,
                dismissed_by_entry=dismissed_by_entry,
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
                    by_course=by_course,
                    by_cohort=by_cohort,
                    prices=state.prices,
                )
            )

        # Fim do período: notas (eq. 33), retorno de créditos (eqs. 34-36) e
        # conclusão de curso (eq. 40).
        approvals: dict[str, int] = {d.name: 0 for d in config.disciplines}
        attempt_log: dict[tuple[str, str], tuple[int, float]] = {}
        # gamma_{a,x}^(t) por disciplina (para o histórico) e sua soma por aluno
        # (para o recorte por curso).
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
                    base_grades[(student.id, name)], attempt, config.learning_gain
                )
                student.grades[name] = max(student.grades.get(name, 0.0), grade)
                attempt_log[(student.id, name)] = (attempt, student.grades[name])
                if student.grades[name] >= config.min_grade:
                    approvals[name] += 1
                gamma = credit_return(
                    config.credit_return,
                    paid=paid.get((student.id, name), 0),
                    grade=student.grades[name],
                    min_grade=config.min_grade,
                )
                returned_by_discipline[(student.id, name)] = gamma
                returned += gamma
            credits_returned[student.id] = returned
            # eq. (36): o que sobrou do período é carregado e soma-se ao
            # retorno total Gamma_a^(t) = Gamma_min + soma gamma_{a,x} (eq. 35).
            student.credits = student.credits - spent[student.id] + config.base_credits + returned

            course = course_by_name[student.course]
            counts_for_graduation = set(course.required) | set(course.electives)
            approved = student.approved(config.min_grade)
            curriculum_hours = sum(hours[name] for name in approved & counts_for_graduation)
            # Conclusão — eq. (40): aprovado em todas as obrigatórias e com a
            # carga horária curricular exigida. Disciplinas livres não contam.
            if set(course.required) <= approved and curriculum_hours >= course.hours_to_graduate:
                student.graduated_at = period
                graduated_so_far[course.name] += 1
                entry = student.entry_period
                graduated_by_entry[(course.name, entry)] = (
                    graduated_by_entry.get((course.name, entry), 0) + 1
                )
                graduated_now += 1

        # Jubilamento: quem completou `max_residence` períodos desde o ingresso
        # sem concluir sai do conjunto ativo. Percorre `enrolled`, não `active`:
        # quem ficou sem nenhuma disciplina elegível não deu lance neste período
        # mas continua cumprindo prazo — e é justamente ele que, sem isto,
        # ficaria disputando para sempre sem nunca sair.
        #
        # A ordem importa: a conclusão (eq. 40) já foi decidida acima, então
        # quem se forma no último período a que tem direito se forma, não é
        # jubilado. O desligamento vale a partir do fim de t, de modo que a
        # satisfação do aluno em t ainda entra nas métricas do período — contar
        # só os que ficam faria o mecanismo parecer melhor por ter expulsado
        # justamente quem servia pior.
        dismissed_now = 0
        if config.max_residence > 0:
            for student in enrolled:
                if student.graduated_at is not None:
                    continue
                if period - student.entry_period + 1 < config.max_residence:
                    continue
                student.dismissed_at = period
                dismissed_so_far[student.course] += 1
                entry = student.entry_period
                dismissed_by_entry[(student.course, entry)] = (
                    dismissed_by_entry.get((student.course, entry), 0) + 1
                )
                dismissed_now += 1

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
            course = course_by_name[student.course]
            requests = []
            for name, utility in sorted(
                utilities[student.id].items(), key=lambda item: -item[1]
            ):
                attempt = attempt_log.get((student.id, name))
                requests.append(
                    RequestRecord(
                        discipline=name,
                        kind=_curriculum_kind(course, name),
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
                    dismissed=student.dismissed_at == period,
                )
            )

        # `grade_averages` é o CR vigente no início do período — o que estava
        # valendo durante os leilões. As notas deste período só entram no CR do
        # período seguinte, como acontece numa matrícula de verdade.
        overall, by_course, by_cohort = _snapshot_courses(
            config=config,
            active=active,
            satisfactions=period_satisfaction,
            grade_averages=grade_averages,
            scarcities=scarcities,
            contentions=contentions,
            won=won,
            total_seats=total_seats,
            entered=entered,
            graduated_so_far=graduated_so_far,
            graduated_by_entry=graduated_by_entry,
            dismissed_so_far=dismissed_so_far,
            dismissed_by_entry=dismissed_by_entry,
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
                    by_course=by_course,
                    by_cohort=by_cohort,
                    prices=_price_stats(list(period_prices.values())),
                ),
                disciplines=[
                    DisciplineSnapshot(
                        name=d.name,
                        seats=d.seats,
                        filled=d.seats - seats[d.name],
                        mean_price=period_prices.get(d.name),
                        approvals=approvals[d.name],
                    )
                    for d in config.disciplines
                ],
                graduated_now=graduated_now,
                dismissed_now=dismissed_now,
            )
        )

    return SimulationResult(
        periods=periods,
        students=[
            StudentSummary(
                id=s.id,
                name=s.name,
                course=s.course,
                entry_period=s.entry_period,
                grade_average=s.grade_average(hours),
                approved_hours=s.approved_hours(hours, config.min_grade),
                hours_to_graduate=course_by_name[s.course].hours_to_graduate,
                credits=s.credits,
                enrollments=enrollments[s.id],
                approvals=len(s.approved(config.min_grade)),
                mean_satisfaction=(
                    sum(satisfaction_history[s.id]) / len(satisfaction_history[s.id])
                    if satisfaction_history[s.id]
                    else 0.0
                ),
                graduated_at=s.graduated_at,
                dismissed_at=s.dismissed_at,
            )
            for s in students
        ],
        histories=[
            StudentHistory(student_id=s.id, periods=history[s.id]) for s in students
        ],
        courses=[c.name for c in config.courses],
        disciplines=[d.name for d in config.disciplines],
    )
