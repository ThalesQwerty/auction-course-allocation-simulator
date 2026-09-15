"""Leilão por créditos — versão simples de uma única rodada (Seção 7.1).

Cada agente distribui livremente seu orçamento de créditos entre lances nas
disciplinas que deseja (respeitando a restrição de orçamento, eq. 19). O
resolvedor de PLI (wdp_solver.solve_wdp) decide a alocação vencedora com base
em preferências derivadas dos lances somados ao desempate, viés e
perturbação estocástica (eq. 22). Em seguida calculam-se os preços de
mercado — 2º preço, eq. 24 — e o consumo de créditos de cada vencedor
(eq. 25).

Escopo desta versão: um único período, uma única rodada de alocação (sem o
loop multi-rodada da Seção 3.2, sem a camada multi-período da Seção 7.2).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .entities import Agent, Allocation, Demand, Good, MutualExclusion, Problem
from .tie_breaking import rectify_bias, stochastic_perturbations, tie_break_factor
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
    """Insumos do leilão de uma rodada.

    `tie_break_order` mapeia good_id -> lista de agent_id em ordem de
    prioridade de desempate (matriz alpha, eq. 20). Se omitido para um bem,
    usa-se a ordem lexicográfica dos ids como padrão determinístico.

    `bias` mapeia (agent_id, good_id) -> viés bruto beta_{a,x} (eq. 21).
    Pares ausentes são tratados como 0 (sem viés).
    """

    agents: list[Agent]
    goods: list[Good]
    budgets: dict[str, int]  # C_a — orçamento de créditos de cada agente, eq. (19)
    bids: list[Bid]
    exclusions: list[MutualExclusion] = field(default_factory=list)
    tie_break_order: dict[str, list[str]] = field(default_factory=dict)
    bias: dict[tuple[str, str], int] = field(default_factory=dict)
    seed: int = 0

    def __post_init__(self) -> None:
        agent_ids = {a.id for a in self.agents}
        missing_budget = agent_ids - self.budgets.keys()
        if missing_budget:
            raise ValueError(f"agentes sem orçamento definido: {missing_budget}")

        total_bid: dict[str, int] = {}
        for bid in self.bids:
            total_bid[bid.agent_id] = total_bid.get(bid.agent_id, 0) + bid.credits
        over_budget = {
            agent_id: (spent, self.budgets[agent_id])
            for agent_id, spent in total_bid.items()
            if agent_id in self.budgets and spent > self.budgets[agent_id]
        }
        if over_budget:
            raise ValueError(
                f"lances excedem o orçamento do agente (eq. 19): {over_budget}"
            )


@dataclass
class AuctionResult:
    bids: dict[tuple[str, str], int]
    allocation: Allocation  # z — eq. (1)
    prices: dict[str, float]  # pi_x — eq. (24)
    consumption: dict[tuple[str, str], float]  # delta_{a,x} — eq. (25)
    remaining_budget: dict[str, float]  # C_a - Delta_a — eq. (27)


def _compute_prices(
    *, goods: list[Good], bids: dict[tuple[str, str], int], allocation: Allocation
) -> dict[str, float]:
    """Preço de mercado por bem — eq. (24): maior lance mal-sucedido, ou 1."""
    prices: dict[str, float] = {}
    for good in goods:
        unsuccessful_bids = [
            credits
            for (agent_id, good_id), credits in bids.items()
            if good_id == good.id and allocation.get((agent_id, good_id), 0) == 0
        ]
        prices[good.id] = float(max(unsuccessful_bids)) if unsuccessful_bids else 1.0
    return prices


def _compute_consumption(
    *, bids: dict[tuple[str, str], int], allocation: Allocation, prices: dict[str, float]
) -> dict[tuple[str, str], float]:
    """Consumo de créditos por demanda vencedora — eq. (25)."""
    consumption: dict[tuple[str, str], float] = {}
    for (agent_id, good_id), credits in bids.items():
        if allocation.get((agent_id, good_id), 0):
            price = prices[good_id]
            consumption[(agent_id, good_id)] = price if credits >= price else float(credits)
    return consumption


def run_auction(auction_input: AuctionInput) -> AuctionResult:
    """Executa uma rodada de leilão: resolve o WDP e liquida preços/consumo."""
    bids = {(b.agent_id, b.good_id): b.credits for b in auction_input.bids}
    if not bids:
        return AuctionResult({}, {}, {}, {}, dict(auction_input.budgets))

    # Preferências finais: lance + viés + desempate + perturbação — eq. (22)
    rectified_bias = rectify_bias(auction_input.bias)
    epsilon = stochastic_perturbations(
        list(bids.keys()),
        num_agents=len(auction_input.agents),
        num_goods=len(auction_input.goods),
        seed=auction_input.seed,
    )

    demands: list[Demand] = []
    for (agent_id, good_id), credits in bids.items():
        order = auction_input.tie_break_order.get(good_id) or sorted(
            a.id for a in auction_input.agents
        )
        rank = order.index(agent_id) + 1 if agent_id in order else len(order)
        alpha_hat = tie_break_factor(rank, len(auction_input.agents))
        beta_hat = rectified_bias.get((agent_id, good_id), 0)
        pref = credits + beta_hat + alpha_hat + epsilon.get((agent_id, good_id), 0.0)
        demands.append(Demand(agent_id, good_id, pref))

    problem = Problem(
        agents=auction_input.agents,
        goods=auction_input.goods,
        demands=demands,
        exclusions=auction_input.exclusions,
    )
    allocation = solve_wdp(problem)

    # Preços de mercado e consumo de créditos — eq. (24)-(26)
    prices = _compute_prices(goods=auction_input.goods, bids=bids, allocation=allocation)
    consumption = _compute_consumption(bids=bids, allocation=allocation, prices=prices)

    remaining_budget = dict(auction_input.budgets)
    for (agent_id, _good_id), consumed in consumption.items():
        remaining_budget[agent_id] -= consumed

    return AuctionResult(
        bids=bids,
        allocation=allocation,
        prices=prices,
        consumption=consumption,
        remaining_budget=remaining_budget,
    )
