"""Uma rodada do leilão por créditos (Seção 7.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from .entities import Agent, Allocation, Demand, Good, MutualExclusion, Problem
from .equations import (
    consumption,
    market_prices,
    remaining_budget,
    remaining_capacity,
    stochastic_perturbations,
)
from .wdp_solver import solve_wdp


@dataclass(frozen=True)
class Bid:
    """Um lance em créditos: c_{a,x} > 0 — eq. (18)."""

    agent_id: str
    good_id: str
    credits: int

    def __post_init__(self) -> None:
        if self.credits <= 0:
            raise ValueError("Bid.credits must be > 0 (eq. 18)")


@dataclass
class AuctionInput:
    """Insumos de uma rodada."""

    agents: list[Agent]
    goods: list[Good]
    budgets: dict[str, int]
    bids: list[Bid]
    exclusions: list[MutualExclusion] = field(default_factory=list)
    conflicts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    epsilon: dict[tuple[str, str], float] | None = None
    seed: int = 0
    time_limit: float | None = None

    def __post_init__(self) -> None:
        missing = {a.id for a in self.agents} - self.budgets.keys()
        if missing:
            raise ValueError(f"agentes sem orçamento definido: {missing}")

        committed: dict[str, int] = {}
        for bid in self.bids:
            committed[bid.agent_id] = committed.get(bid.agent_id, 0) + bid.credits
        over_budget = {
            agent_id: (spent, self.budgets[agent_id])
            for agent_id, spent in committed.items()
            if agent_id in self.budgets and spent > self.budgets[agent_id]
        }
        if over_budget:
            raise ValueError(f"lances excedem o orçamento do agente (eq. 19): {over_budget}")


@dataclass
class AuctionResult:
    bids: dict[tuple[str, str], int]
    allocation: Allocation
    prices: dict[str, int]
    consumption: dict[tuple[str, str], int]
    remaining_budget: dict[str, int]
    remaining_capacity: dict[str, float]
    solver_seconds: float = 0.0


def _demands(auction_input: AuctionInput, bids: dict[tuple[str, str], int]) -> list[Demand]:
    """Os pares de demanda: a preferência é o **lance**, e o ε vai à parte."""
    epsilon = auction_input.epsilon
    if epsilon is None:
        epsilon = stochastic_perturbations(
            list(bids),
            num_agents=len(auction_input.agents),
            num_goods=len(auction_input.goods),
            seed=auction_input.seed,
        )
    return [
        Demand(agent_id, good_id, credits, epsilon.get((agent_id, good_id), 0.0))
        for (agent_id, good_id), credits in bids.items()
    ]


def run_auction(auction_input: AuctionInput) -> AuctionResult:
    """Resolve o WDP da rodada por PLI e liquida preços, consumo e saldos."""
    bids = {(b.agent_id, b.good_id): b.credits for b in auction_input.bids}
    capacity = {a.id: a.capacity for a in auction_input.agents}
    if not bids:
        return AuctionResult({}, {}, {}, {}, dict(auction_input.budgets), capacity)

    problem = Problem(
        agents=auction_input.agents,
        goods=auction_input.goods,
        demands=_demands(auction_input, bids),
        exclusions=auction_input.exclusions,
    )
    started = perf_counter()
    allocation = solve_wdp(problem, time_limit=auction_input.time_limit)
    solver_seconds = perf_counter() - started

    prices = market_prices(
        good_ids=[g.id for g in auction_input.goods],
        bids=bids,
        allocation=allocation,
    )
    consumed = consumption(bids=bids, allocation=allocation, prices=prices)

    return AuctionResult(
        bids=bids,
        allocation=allocation,
        prices=prices,
        consumption=consumed,
        remaining_budget=remaining_budget(
            budgets=auction_input.budgets, consumption=consumed
        ),
        remaining_capacity=remaining_capacity(
            capacity=capacity,
            allocation={key: 1 for key in consumed},
            weights={g.id: g.weight for g in auction_input.goods},
        ),
        solver_seconds=solver_seconds,
    )
