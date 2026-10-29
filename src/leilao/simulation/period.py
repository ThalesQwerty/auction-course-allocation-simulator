"""Um período letivo inteiro: da matrícula garantida ao relatório.

    u^(t) recortado ao elegível                  eqs. (41)-(43)
    matrícula garantida dos ingressantes         (fora do leilão)
    para cada rodada r:  mensagem → alocação → descontos
    notas, retorno de créditos, conclusão        eqs. (33)-(36), (40)
    relatórios do período e os sinais do próximo
"""
from __future__ import annotations

from dataclasses import dataclass

from ..behavior import utility_matrix
from ..config import SimulationConfig
from ..equations import (
    Signals,
    demand_per_seat,
    mean_price,
    pass_rate_estimate,
    satisfaction,
    win_estimate,
)
from ..population import Student
from .closing import PeriodClosing, close_period
from .reports import (
    DisciplineSnapshot,
    PeriodReport,
    PriceStats,
    RequestRecord,
    RoundReport,
    StudentPeriodRecord,
)
from .rounds import RoundOutcome, run_round
from .setup import Draws
from .snapshots import Axis, measure, snapshot_groups
from .state import PeriodState


@dataclass(frozen=True)
class PeriodOutcome:
    report: PeriodReport
    records: dict[str, StudentPeriodRecord]
    satisfaction: dict[str, float]
    first_grades: list[float]
    # O que este período publica para o próximo ler.
    signals: Signals


def _scarcities(
    *,
    active: list[Student],
    utilities: dict[str, dict[str, float]],
    config_seats: dict[str, int],
) -> dict[str, float]:
    """Escassez: elegíveis por vaga, na média das disciplinas que o aluno
    ainda pode cursar.

    Conta toda a universidade em "quantos querem", e não só o recorte: quem
    disputa uma vaga com o aluno não é só quem está na geração dele.
    Disciplina sem vaga fica de fora — não é oferta, e a razão seria divisão
    por zero.
    """
    eligible = {
        s.id: [n for n in utilities[s.id] if config_seats[n] > 0] for s in active
    }
    count: dict[str, int] = {}
    for student in active:
        for name in eligible[student.id]:
            count[name] = count.get(name, 0) + 1
    return {
        s.id: demand_per_seat(
            demands=[count[n] / config_seats[n] for n in eligible[s.id]]
        )
        for s in active
    }


def _contentions(
    *, active: list[Student], state: PeriodState
) -> tuple[dict[str, float], dict[str, int]]:
    """Concorrência: solicitantes por vaga nas disciplinas que o aluno pediu.

    Como a escassez, é do período inteiro e usa a oferta do início dele, então
    também não anda entre as rodadas. Devolve também a contagem por
    disciplina, que o relatório por disciplina publica como `requests`.
    """
    requested = {s.id: state.requested(s.id) for s in active}
    demand: dict[str, int] = {}
    for student in active:
        for name in requested[student.id]:
            demand[name] = demand.get(name, 0) + 1
    contentions = {
        # Uma disciplina sem vaga nunca entra em B_a^(t,r), então quem está
        # aqui tem q_x >= 1.
        s.id: demand_per_seat(
            demands=[demand[n] / state.config_seats[n] for n in requested[s.id]]
        )
        for s in active
    }
    return contentions, demand


def _publish_signals(
    *,
    config: SimulationConfig,
    draws: Draws,
    state: PeriodState,
    closing: PeriodClosing,
    demand: dict[str, int],
) -> Signals:
    """Os sinais do próximo período, saídos do que este acabou de publicar.

    É todo o conjunto de informação do aluno sobre a disciplina, e é o mesmo
    que um aluno real lê. As fórmulas estão em `equations.win_estimate` e
    `equations.pass_rate_estimate`.
    """
    return Signals(
        win={
            d.name: win_estimate(seats=d.seats, requests=demand.get(d.name, 0))
            for d in config.disciplines
        },
        pass_rate={
            d.name: pass_rate_estimate(
                approvals=closing.approvals[d.name],
                enrolled=d.seats - state.seats[d.name],
            )
            for d in config.disciplines
        },
        hours=draws.hours,
        reach=draws.reach,
    )


def _request_records(
    *,
    student: Student,
    utilities: dict[str, float],
    state: PeriodState,
    closing: PeriodClosing,
    config: SimulationConfig,
) -> list[RequestRecord]:
    """Uma linha por disciplina que o aluno quis — a tela de depuração.

    Ordenação **estável** sobre um dicionário que já vem na ordem da grade:
    utilidades empatadas saem na ordem de listagem do cenário, a mesma que
    desempata as duas mochilas.
    """
    records: list[RequestRecord] = []
    for name, utility in sorted(utilities.items(), key=lambda item: -item[1]):
        attempt = closing.attempts.get((student.id, name))
        records.append(
            RequestRecord(
                discipline=name,
                utility=utility,
                bids=state.bid_log[student.id].get(name, [0] * config.rounds),
                won_round=state.won_round.get((student.id, name)),
                paid=state.paid.get((student.id, name), 0),
                attempt=attempt[0] if attempt else None,
                grade=attempt[1] if attempt else None,
                approved=bool(attempt and attempt[1] >= config.min_grade),
                returned=closing.returned.get((student.id, name), 0),
            )
        )
    return records


@dataclass(frozen=True)
class _Reporter:
    """Monta um `RoundReport` a partir do que muda no instante.

    O contexto que **não** muda dentro do período — quem está ativo, o eixo
    das gerações, as utilidades, a escassez e a concorrência — fica guardado
    aqui, de modo que cada chamada passe só o instante.
    """

    config: SimulationConfig
    draws: Draws
    period: int
    active: list[Student]
    axis: Axis
    state: PeriodState
    utilities: dict[str, dict[str, float]]
    grade_averages: dict[str, float]
    scarcities: dict[str, float]
    contentions: dict[str, float]

    def at(
        self,
        *,
        round_number: int,
        satisfactions: dict[str, float],
        won: dict[str, set[str]],
        credits: dict[str, int],
        bids: dict[str, int],
        prices: PriceStats | None,
        ages: dict[str, int],
        credit_returns: dict[str, int] | None,
    ) -> RoundReport:
        values = measure(
            config=self.config,
            active=self.active,
            satisfactions=satisfactions,
            grade_averages=self.grade_averages,
            scarcities=self.scarcities,
            contentions=self.contentions,
            won=won,
            messages=self.state.messages(),
            utilities=self.utilities,
            credits=credits,
            supply=self.state.credits_start,
            bids=bids,
            ages=ages,
            hours=self.draws.hours,
            credit_returns=credit_returns,
        )
        overall, by_cohort = snapshot_groups(
            config=self.config,
            active=self.active,
            students=self.draws.students,
            period=self.period,
            axis=self.axis,
            values=values,
            total_seats=self.draws.total_seats,
        )
        return RoundReport(
            period=self.period,
            round=round_number,
            overall=overall,
            by_cohort=by_cohort,
            prices=prices,
        )

    def ages(self, *, closed: bool) -> dict[str, int]:
        """A idade do aluno no instante do recorte.

        Em plena rodada de t ele completou t - t_a periodos: o que cursa
        agora ainda nao foi avaliado. Ao fim de t, com as notas ja saidas, o
        periodo conta como completo.
        """
        return {
            s.id: self.period - s.entry_period + (1 if closed else 0)
            for s in self.active
        }


def _period_prices(*, config: SimulationConfig, state: PeriodState) -> dict[str, float]:
    """O preço do período de cada disciplina que esteve no mercado."""
    prices: dict[str, float] = {}
    for discipline in config.disciplines:
        price = mean_price(
            price_sum=state.price_sum[discipline.name],
            rounds_on_market=state.price_rounds[discipline.name],
        )
        if price is not None:
            prices[discipline.name] = price
    return prices


def _discipline_snapshots(
    *,
    config: SimulationConfig,
    draws: Draws,
    state: PeriodState,
    closing: PeriodClosing,
    demand: dict[str, int],
    prices: dict[str, float],
) -> list[DisciplineSnapshot]:
    return [
        DisciplineSnapshot(
            name=d.name,
            curriculum_period=draws.curriculum[d.name],
            hours=d.hours,
            seats=d.seats,
            filled=d.seats - state.seats[d.name],
            granted=state.granted[d.name],
            requests=demand.get(d.name, 0),
            mean_price=prices.get(d.name),
            approvals=closing.approvals[d.name],
        )
        for d in config.disciplines
    ]


def _student_records(
    *,
    config: SimulationConfig,
    draws: Draws,
    active: list[Student],
    state: PeriodState,
    closing: PeriodClosing,
    period: int,
    utilities: dict[str, dict[str, float]],
    grade_averages: dict[str, float],
    satisfactions: dict[str, float],
) -> dict[str, StudentPeriodRecord]:
    return {
        student.id: StudentPeriodRecord(
            period=period,
            credits_start=state.credits_start[student.id],
            credits_spent=state.spent[student.id],
            credits_returned=closing.credits_returned[student.id],
            credits_end=student.credits,
            satisfaction=satisfactions[student.id],
            grade_average=grade_averages[student.id],
            approved_hours=student.approved_hours(draws.hours, config.min_grade),
            enrolled_hours=sum(draws.hours[name] for name in state.won[student.id]),
            requests=_request_records(
                student=student,
                utilities=utilities[student.id],
                state=state,
                closing=closing,
                config=config,
            ),
            graduated=student.graduated_at == period,
        )
        for student in active
    }


def run_period(
    *,
    config: SimulationConfig,
    draws: Draws,
    period: int,
    active: list[Student],
    signals: Signals,
    enrollments: dict[str, int],
) -> PeriodOutcome | None:
    """Roda o período. `None` quando não há ninguém a medir — e aí a
    simulação para, porque um período sem aluno só produziria zeros
    enganosos.
    """
    utilities = {
        s.id: utility_matrix(
            row=draws.utility_rows[(s.id, period)], student=s, config=config
        )
        for s in active
    }
    # Guarda, não caso de uso: nada é elegível só para quem aprovou a grade
    # inteira, que já saiu por `graduated_at` e nem chega aqui. Sem ela, uma
    # grade degenerada publicaria um período de satisfação zero em vez de
    # simplesmente não publicar período nenhum.
    active = [s for s in active if utilities[s.id]]
    if not active:
        return None

    grade_averages = {s.id: s.grade_average(draws.hours) for s in active}
    state = PeriodState.opening(config=config, active=active)
    scarcities = _scarcities(
        active=active, utilities=utilities, config_seats=state.config_seats
    )

    for student in (s for s in active if s.entry_period == period):
        state.enroll_newcomer(
            student.id,
            entry_courses=draws.entry_courses,
            hours=draws.hours,
            uses_credits=config.uses_credits,
        )

    outcomes = [
        run_round(
            config=config,
            draws=draws,
            active=active,
            utilities=utilities,
            grade_averages=grade_averages,
            signals=signals,
            state=state,
            round_number=number,
        )
        for number in range(1, config.rounds + 1)
    ]

    # A concorrência depende dos lances de **todas** as rodadas, então os
    # relatórios de rodada só podem ser montados depois do laço.
    contentions, demand = _contentions(active=active, state=state)
    reporter = _Reporter(
        config=config,
        draws=draws,
        period=period,
        active=active,
        axis=Axis.cohorts(draws.entry_periods, period),
        state=state,
        utilities=utilities,
        grade_averages=grade_averages,
        scarcities=scarcities,
        contentions=contentions,
    )

    during = reporter.ages(closed=False)
    round_reports = [
        reporter.at(
            round_number=outcome.number,
            satisfactions=outcome.satisfaction,
            won=outcome.won,
            credits=outcome.budget,
            bids=outcome.bids,
            prices=outcome.prices,
            ages=during,
            credit_returns=None,
        )
        for outcome in outcomes
    ]

    closing = close_period(
        config=config,
        draws=draws,
        active=active,
        state=state,
        period=period,
        enrollments=enrollments,
    )

    period_satisfaction = {
        s.id: satisfaction(utilities=utilities[s.id], allocated=sorted(state.won[s.id]))
        for s in active
    }
    prices = _period_prices(config=config, state=state)

    # `grade_averages` continua sendo o CR vigente no **início** do período —
    # o que estava valendo durante os leilões. As notas de t só entram no CR
    # do período seguinte, como numa matrícula de verdade.
    aggregate = reporter.at(
        round_number=0,
        satisfactions=period_satisfaction,
        won=state.won,
        credits=state.budget,
        bids=state.bid_total,
        prices=PriceStats.of(list(prices.values())),
        ages=reporter.ages(closed=True),
        credit_returns=closing.credits_returned,
    )

    return PeriodOutcome(
        report=PeriodReport(
            period=period,
            rounds=round_reports,
            aggregate=aggregate,
            disciplines=_discipline_snapshots(
                config=config,
                draws=draws,
                state=state,
                closing=closing,
                demand=demand,
                prices=prices,
            ),
            graduated_now=closing.graduated_now,
        ),
        records=_student_records(
            config=config,
            draws=draws,
            active=active,
            state=state,
            closing=closing,
            period=period,
            utilities=utilities,
            grade_averages=grade_averages,
            satisfactions=period_satisfaction,
        ),
        satisfaction=period_satisfaction,
        first_grades=closing.first_grades,
        signals=_publish_signals(
            config=config, draws=draws, state=state, closing=closing, demand=demand
        ),
    )
