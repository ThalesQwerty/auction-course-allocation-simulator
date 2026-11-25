"""Um período letivo inteiro: da matrícula garantida ao relatório."""
from __future__ import annotations

from dataclasses import dataclass

from ..behavior import interest_total, utility_matrix
from ..config import SimulationConfig
from ..equations import (
    Behavior,
    demand_per_seat,
    entry_class,
    mean_price,
    reserve_threshold,
    satisfaction,
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

CELL_AXIS = "cell:"


@dataclass(frozen=True)
class PeriodOutcome:
    report: PeriodReport
    records: dict[str, StudentPeriodRecord]
    satisfaction: dict[str, float]
    first_grades: list[float]


def _scarcities(
    *,
    active: list[Student],
    utilities: dict[str, dict[str, float]],
    config_seats: dict[str, int],
) -> dict[str, float]:
    """Escassez: elegíveis por vaga, na média das disciplinas que o aluno"""
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
    """Concorrência: solicitantes por vaga nas disciplinas que o aluno pediu."""
    requested = {s.id: state.requested(s.id) for s in active}
    demand: dict[str, int] = {}
    for student in active:
        for name in requested[student.id]:
            demand[name] = demand.get(name, 0) + 1
    contentions = {
        s.id: demand_per_seat(
            demands=[demand[n] / state.config_seats[n] for n in requested[s.id]]
        )
        for s in active
    }
    return contentions, demand


def _eligible_count(
    utilities: dict[str, dict[str, float]],
) -> dict[str, int]:
    """Quantos alunos tinham cada disciplina no conjunto elegível."""
    count: dict[str, int] = {}
    for row in utilities.values():
        for name in row:
            count[name] = count.get(name, 0) + 1
    return count


def _request_records(
    *,
    student: Student,
    utilities: dict[str, float],
    state: PeriodState,
    closing: PeriodClosing,
    config: SimulationConfig,
    groups: dict[str, str],
) -> list[RequestRecord]:
    """Uma linha por **turma** que o aluno quis — a tela de depuração."""
    records: list[RequestRecord] = []
    excluded = set(closing.excluded.get(student.id, ()))
    taken = closing.retained.get(student.id, set())
    for name, utility in sorted(utilities.items(), key=lambda item: -item[1]):
        attempt = (
            closing.attempts.get((student.id, groups[name]))
            if name in taken
            else None
        )
        records.append(
            RequestRecord(
                discipline=name,
                utility=utility,
                bids=state.bid_log[student.id].get(name, [0] * config.rounds),
                won_round=state.won_round.get((student.id, name)),
                paid=state.paid.get((student.id, name), 0),
                excluded=name in excluded,
                attempt=attempt[0] if attempt else None,
                grade=attempt[1] if attempt else None,
                approved=bool(attempt and attempt[1] >= config.min_grade),
                returned=closing.returned.get((student.id, name), 0),
            )
        )
    return records


@dataclass(frozen=True)
class _Reporter:
    """Monta um `RoundReport` a partir do que muda no instante."""

    config: SimulationConfig
    draws: Draws
    period: int
    active: list[Student]
    axis: Axis
    profiles: dict[str, Axis]
    state: PeriodState
    utilities: dict[str, dict[str, float]]
    grade_averages: dict[str, float]
    reserves: dict[str, float]
    scarcities: dict[str, float]
    contentions: dict[str, float]

    @property
    def cells(self) -> dict[str, Axis]:
        """Os eixos de perfil cruzados com a coorte — ver `Axis.crossed`."""
        return {
            name: Axis.crossed(axis, self.axis) for name, axis in self.profiles.items()
        }

    def at(
        self,
        *,
        round_number: int,
        satisfactions: dict[str, float],
        won: dict[str, set[str]],
        credits: dict[str, int],
        bids: dict[str, int],
        prices: PriceStats | None,
        allocation_seconds: float,
        ages: dict[str, int],
        credit_returns: dict[str, int] | None,
        allocated_satisfactions: dict[str, float] | None = None,
        retained: dict[str, set[str]] | None = None,
        excluded: dict[str, list[str]] | None = None,
    ) -> RoundReport:
        requested = {s.id: self.state.requested(s.id) for s in self.active}
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
            discipline_hours=self.draws.discipline_hours,
            credit_returns=credit_returns,
            selectivities={
                s.id: self.draws.selectivity[s.id] for s in self.active
            },
            reserves=self.reserves,
            allocated_satisfactions=allocated_satisfactions,
            retained=retained,
            excluded=excluded,
            requested=requested,
        )
        cells = {f"{CELL_AXIS}{name}": axis for name, axis in self.cells.items()}
        overall, groups = snapshot_groups(
            config=self.config,
            active=self.active,
            students=self.draws.students,
            period=self.period,
            axes={"cohort": self.axis, **self.profiles, **cells},
            values=values,
            total_seats=self.draws.total_seats,
        )
        return RoundReport(
            period=self.period,
            round=round_number,
            overall=overall,
            by_cohort=groups.pop("cohort"),
            by_cell={
                name.removeprefix(CELL_AXIS): snapshots
                for name, snapshots in groups.items()
                if name.startswith(CELL_AXIS)
            },
            by_profile={
                name: snapshots
                for name, snapshots in groups.items()
                if not name.startswith(CELL_AXIS)
            },
            prices=prices,
            allocation_seconds=allocation_seconds,
        )

    def ages(self, *, closed: bool) -> dict[str, int]:
        """A idade do aluno no instante do recorte."""
        return {
            s.id: self.period - s.entry_period + (1 if closed else 0)
            for s in self.active
        }


def _period_prices(*, config: SimulationConfig, state: PeriodState) -> dict[str, float]:
    """O preço do período de cada **turma** que esteve no mercado."""
    prices: dict[str, float] = {}
    for name in config.seats_by_class():
        price = mean_price(
            price_sum=state.price_sum[name],
            rounds_on_market=state.price_rounds[name],
        )
        if price is not None:
            prices[name] = price
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
    by_name = {d.name: d for d in config.disciplines}
    return [
        DisciplineSnapshot(
            name=name,
            discipline=draws.discipline_of[name],
            curriculum_period=draws.curriculum[draws.discipline_of[name]],
            hours=draws.hours[name],
            classes=by_name[draws.discipline_of[name]].classes,
            schedule=draws.schedule_of[name],
            elective=by_name[draws.discipline_of[name]].elective,
            seats=seats,
            filled=seats - state.seats[name],
            granted=state.granted[name],
            requests=demand.get(name, 0),
            mean_price=prices.get(name),
            approvals=closing.approvals[name],
            exclusions=closing.exclusions[name],
        )
        for name, seats in draws.seats.items()
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
            approved_hours=student.approved_hours(
                draws.discipline_hours, config.min_grade
            ),
            enrolled_hours=sum(draws.hours[name] for name in state.won[student.id]),
            retained_hours=sum(
                draws.hours[name] for name in closing.retained[student.id]
            ),
            effective_load=closing.load[student.id],
            requests=_request_records(
                student=student,
                utilities=utilities[student.id],
                state=state,
                closing=closing,
                config=config,
                groups=draws.discipline_of,
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
    enrollments: dict[str, int],
    keep_records: bool = True,
) -> PeriodOutcome | None:
    """Roda o período. `None` quando não há ninguém a medir — e aí a"""
    for student in active:
        student.behavior = Behavior(
            selectivity=draws.selectivity[student.id]
        )

    utilities = {
        s.id: utility_matrix(
            interest=draws.interest_rows[(s.id, period)],
            student=s,
            config=config,
            schedule_interest=draws.schedule_rows[(s.id, period)],
        )
        for s in active
    }
    interests = {
        s.id: interest_total(
            interest=draws.interest_rows[(s.id, period)],
            student=s,
            config=config,
        )
        for s in active
    }
    active = [s for s in active if utilities[s.id]]
    if not active:
        return None

    grade_averages = {s.id: s.grade_average(draws.discipline_hours) for s in active}
    reserves = {
        s.id: reserve_threshold(
            selectivity=draws.selectivity[s.id], interest=interests[s.id]
        )
        for s in active
    }
    state = PeriodState.opening(config=config, active=active)
    scarcities = _scarcities(
        active=active, utilities=utilities, config_seats=state.config_seats
    )

    newcomers = [s for s in active if s.entry_period == period]
    for ordinal, student in enumerate(newcomers):
        state.enroll_newcomer(
            student.id,
            entry_courses=[
                entry_class(
                    ordinal=ordinal,
                    cohort=len(newcomers),
                    classes=draws.classes[discipline],
                    offset=draws.entry_offsets.get(discipline, 0),
                )
                for discipline in draws.entry_courses
            ],
            hours=draws.hours,
            uses_credits=config.uses_credits,
        )

    outcomes = [
        run_round(
            config=config,
            draws=draws,
            active=active,
            utilities=utilities,
            interests=interests,
            grade_averages=grade_averages,
            state=state,
            round_number=number,
        )
        for number in range(1, config.rounds + 1)
    ]

    contentions, demand = _contentions(active=active, state=state)
    reporter = _Reporter(
        config=config,
        draws=draws,
        period=period,
        active=active,
        axis=Axis.cohorts(draws.entry_periods, period),
        profiles=Axis.states(config),
        state=state,
        utilities=utilities,
        grade_averages=grade_averages,
        reserves=reserves,
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
            allocation_seconds=outcome.allocation_seconds,
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
        utilities=utilities,
        enrollments=enrollments,
    )

    period_satisfaction = {
        s.id: satisfaction(
            utilities=utilities[s.id], allocated=sorted(closing.retained[s.id])
        )
        for s in active
    }
    allocated_satisfaction = {
        s.id: satisfaction(
            utilities=utilities[s.id], allocated=sorted(state.won[s.id])
        )
        for s in active
    }
    prices = _period_prices(config=config, state=state)

    aggregate = reporter.at(
        round_number=0,
        satisfactions=period_satisfaction,
        won=state.won,
        credits=state.budget,
        bids=state.bid_total,
        prices=PriceStats.of(list(prices.values())),
        allocation_seconds=sum(o.allocation_seconds for o in outcomes),
        ages=reporter.ages(closed=True),
        credit_returns=closing.credits_returned,
        allocated_satisfactions=allocated_satisfaction,
        retained=closing.retained,
        excluded=closing.excluded,
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
            dismissed_now=closing.dismissed_now,
        ),
        records=(
            _student_records(
                config=config,
                draws=draws,
                active=active,
                state=state,
                closing=closing,
                period=period,
                utilities=utilities,
                grade_averages=grade_averages,
                satisfactions=period_satisfaction,
            )
            if keep_records
            else {}
        ),
        satisfaction=period_satisfaction,
        first_grades=closing.first_grades,
    )
