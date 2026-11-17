"""Uma rodada do leilão por créditos (Seção 7.1).

Cada agente reparte o orçamento em lances (eq. 19), o resolvedor decide a
alocação sobre as preferências da eq. (22), e a liquidação aplica o preço de
segundo preço (eq. 24), o consumo (eq. 25) e os dois descontos (eqs. 14, 27).

Escopo: um período, uma rodada. O laço multi-rodada e a camada multi-período
são de `simulation`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from .config import Resolver
from .entities import Agent, Allocation, Demand, Good, MutualExclusion, Problem
from .equations import (
    consumption,
    market_prices,
    remaining_budget,
    remaining_capacity,
    stochastic_perturbations,
)
from .wdp_solver import solve_wdp, solve_wdp_greedy


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
    """Insumos de uma rodada.

    `epsilon` permite injetar a matriz de perturbações já sorteada. Numa
    simulação multi-rodada ela **precisa** ser a mesma em todas as rodadas
    (Seção 7.1.2); omitida, é sorteada a partir de `seed` para esta rodada.

    Não há mais ordem de desempate (matriz α) nem viés (matriz β): as duas
    saíram do modelo junto com as eqs. (20) e (21) — ver `wdp_solver`.
    """

    agents: list[Agent]
    goods: list[Good]
    budgets: dict[str, int]  # C_a — eq. (19)
    bids: list[Bid]
    exclusions: list[MutualExclusion] = field(default_factory=list)
    # Turma -> os grupos de `E = M ∪ G` a que ela pertence: a disciplina e o
    # horário. Entra no preço — quem foi roteado para outra turma de um grupo
    # em comum não é perdedor nesta.
    conflicts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    epsilon: dict[tuple[str, str], float] | None = None
    seed: int = 0

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
    allocation: Allocation  # z — eq. (1)
    prices: dict[str, int]  # π_x — eq. (24)
    consumption: dict[tuple[str, str], int]  # δ_{a,x} — eq. (25)
    remaining_budget: dict[str, int]  # C_a − Δ_a — eq. (27)
    remaining_capacity: dict[str, float]  # W_a − Σ w_x — eq. (14)
    # Tempo de parede do resolvedor, em segundos. É instrumentação, não
    # grandeza do modelo: nada no simulador a lê para decidir coisa alguma.
    # Cobre montar o problema e resolvê-lo, que é o que `solve_wdp` faz.
    solver_seconds: float = 0.0


def _demands(auction_input: AuctionInput, bids: dict[tuple[str, str], int]) -> list[Demand]:
    """Os pares de demanda: a preferência é o **lance**, e o ε vai à parte.

    Somá-los seria a eq. (22) do anteprojeto, e é justamente o que não se faz
    mais — ver `wdp_solver`.
    """
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


def run_auction(auction_input: AuctionInput, *, resolver: Resolver = "ilp") -> AuctionResult:
    """Resolve o WDP da rodada e liquida preços, consumo e saldos.

    `resolver` escolhe quem decide a alocação — a PLI global do anteprojeto ou
    a varredura gulosa, que é o mecanismo de *bidding points*. É o **único**
    ponto em que as duas células do leilão diferem: preferência, preço e
    consumo são calculados igual dos dois lados.
    """
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
    allocation = (solve_wdp if resolver == "ilp" else solve_wdp_greedy)(problem)
    solver_seconds = perf_counter() - started

    prices = market_prices(
        good_ids=[g.id for g in auction_input.goods],
        bids=bids,
        allocation=allocation,
        conflicts=auction_input.conflicts,
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
