"""Uma rodada de alocação, nos dois mecanismos."""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from ..auction import AuctionInput, Bid, run_auction
from ..behavior import compute_bids
from ..config import SimulationConfig
from ..entities import Agent, Good, MutualExclusion
from ..equations import available_goods, satisfaction
from ..population import Student
from ..ranking import allocate_by_ilp, allocate_by_ranking, request_set
from .reports import PriceStats
from .setup import Draws
from .state import PeriodState

PRICE_FLOOR = 1


@dataclass(frozen=True)
class RoundOutcome:
    """O que varia de uma rodada para a outra."""

    number: int
    satisfaction: dict[str, float]
    won: dict[str, set[str]]
    budget: dict[str, int]
    bids: dict[str, int]
    prices: PriceStats | None
    allocation_seconds: float


def _available(
    *,
    active: list[Student],
    utilities: dict[str, dict[str, float]],
    state: PeriodState,
    hours: dict[str, int],
    conflicts: dict[str, tuple[str, ...]],
) -> dict[str, list[str]]:
    """B_a^(t,r) de cada aluno — ver `equations.available_goods`."""
    return {
        s.id: available_goods(
            eligible=utilities[s.id],
            seats=state.seats,
            hours=hours,
            capacity=state.capacity[s.id],
            already_won=state.won[s.id],
            conflicts=conflicts,
        )
        for s in active
    }


def _run_credit_round(
    *,
    config: SimulationConfig,
    draws: Draws,
    active: list[Student],
    utilities: dict[str, dict[str, float]],
    interests: dict[str, float],
    state: PeriodState,
    available: dict[str, list[str]],
    round_number: int,
    won_now: dict[str, list[str]],
) -> tuple[dict[str, int], float]:
    """O leilão: lances, PLI (ou varredura), preço e consumo."""
    bids: list[Bid] = []
    for student in active:
        posted = compute_bids(
            utilities=utilities[student.id],
            available=available[student.id],
            budget=state.budget[student.id],
            behavior=student.behavior,
            classes=draws.classes,
            interest=interests[student.id],
        )
        for name, credits in posted.items():
            state.record_bid(student.id, name, round_number, credits)
        state.bid_total[student.id] += sum(posted.values())
        bids.extend(Bid(student.id, name, credits) for name, credits in posted.items())

    prices = {
        name: PRICE_FLOOR for name in draws.seats if state.seats[name] > 0
    }
    if not bids:
        return prices, 0.0

    result = run_auction(
        AuctionInput(
            agents=[Agent(s.id, state.capacity[s.id]) for s in active],
            goods=[
                Good(name, state.seats[name], draws.hours[name])
                for name in draws.seats
            ],
            exclusions=[MutualExclusion(clique) for clique in draws.exclusions],
            conflicts=draws.conflicts,
            budgets=state.budget,
            bids=bids,
            epsilon=draws.epsilon,
            seed=config.seed,
        ),
    )
    for (student_id, name), allocated in result.allocation.items():
        if allocated:
            won_now[student_id].append(name)
            state.grant(student_id, name, round_number=round_number, hours=draws.hours)
    for (student_id, name), consumed in result.consumption.items():
        state.charge(student_id, name, consumed)
    for name, price in result.prices.items():
        if name in prices:
            prices[name] = price
    return prices, result.solver_seconds


def _run_ranking_round(
    *,
    config: SimulationConfig,
    draws: Draws,
    active: list[Student],
    utilities: dict[str, dict[str, float]],
    interests: dict[str, float],
    grade_averages: dict[str, float],
    state: PeriodState,
    available: dict[str, list[str]],
    round_number: int,
    won_now: dict[str, list[str]],
) -> float:
    """A linha de base: o aluno resolve a carga (eq. 4) em casa, numa mochila"""
    requests: list[tuple[str, str]] = []
    for student in active:
        for name in request_set(
            utilities=utilities[student.id],
            available=available[student.id],
            hours=draws.hours,
            capacity=int(state.capacity[student.id]),
            behavior=student.behavior,
            classes=draws.classes,
            conflicts=draws.conflicts,
            interest=interests[student.id],
        ):
            state.record_bid(student.id, name, round_number, 1)
            requests.append((student.id, name))

    priority = {s.id: grade_averages[s.id] for s in active}
    tiebreak = draws.student_epsilon
    allocate = allocate_by_ilp if config.uses_credits else allocate_by_ranking
    started = perf_counter()
    allocated = allocate(
        requests=requests,
        priority=priority,
        seats=state.seats,
        hours=draws.hours,
        capacity={s.id: int(state.capacity[s.id]) for s in active},
        conflicts=draws.conflicts,
        tiebreak=tiebreak,
    )
    seconds = perf_counter() - started
    for student_id, name in allocated:
        won_now[student_id].append(name)
        state.grant(student_id, name, round_number=round_number, hours=draws.hours)
    return seconds


def run_round(
    *,
    config: SimulationConfig,
    draws: Draws,
    active: list[Student],
    utilities: dict[str, dict[str, float]],
    interests: dict[str, float],
    grade_averages: dict[str, float],
    state: PeriodState,
    round_number: int,
) -> RoundOutcome:
    available = _available(
        active=active,
        utilities=utilities,
        state=state,
        hours=draws.hours,
        conflicts=draws.conflicts,
    )
    won_now: dict[str, list[str]] = {
        s.id: list(state.guaranteed[s.id]) if round_number == 1 else [] for s in active
    }

    prices: dict[str, int] | None = None
    if config.uses_credits:
        prices, allocation_seconds = _run_credit_round(
            config=config,
            draws=draws,
            active=active,
            utilities=utilities,
            interests=interests,
            state=state,
            available=available,
            round_number=round_number,
            won_now=won_now,
        )
    else:
        allocation_seconds = _run_ranking_round(
            config=config,
            draws=draws,
            active=active,
            utilities=utilities,
            interests=interests,
            grade_averages=grade_averages,
            state=state,
            available=available,
            round_number=round_number,
            won_now=won_now,
        )

    if prices is not None:
        for name, price in prices.items():
            state.price_sum[name] += price
            state.price_rounds[name] += 1

    return RoundOutcome(
        number=round_number,
        satisfaction={
            s.id: satisfaction(
                utilities=utilities[s.id], allocated=won_now[s.id]
            )
            for s in active
        },
        won={s.id: set(won_now[s.id]) for s in active},
        budget=dict(state.budget),
        bids=dict(state.bid_total),
        prices=PriceStats.of(list(prices.values())) if prices is not None else None,
        allocation_seconds=allocation_seconds,
    )
