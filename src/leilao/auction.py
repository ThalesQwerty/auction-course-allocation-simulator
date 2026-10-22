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
from .config import Resolver
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
    """Insumos do leilão de uma rodada.

    `tie_break_order` mapeia good_id -> lista de agent_id em ordem de
    prioridade de desempate (matriz alpha, eq. 20). Se omitido para um bem,
    usa-se a ordem lexicográfica dos ids como padrão determinístico.

    `bias` mapeia (agent_id, good_id) -> viés bruto beta_{a,x} (eq. 21).
    Pares ausentes são tratados como 0 (sem viés).

    `epsilon` permite injetar a matriz de perturbações estocástica já sorteada.
    Numa simulação multi-rodada ela precisa ser a mesma em todas as rodadas
    (Seção 7.1.2); omitida, é sorteada a partir de `seed` para esta rodada.
    """

    agents: list[Agent]
    goods: list[Good]
    budgets: dict[str, int]  # C_a — orçamento de créditos de cada agente, eq. (19)
    bids: list[Bid]
    exclusions: list[MutualExclusion] = field(default_factory=list)
    tie_break_order: dict[str, list[str]] = field(default_factory=dict)
    bias: dict[tuple[str, str], int] = field(default_factory=dict)
    epsilon: dict[tuple[str, str], float] | None = None
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
    prices: dict[str, int]  # pi_x — eq. (24). Sempre inteiro: lances (eq. 18) e o
    # valor-padrão de 1 crédito já são inteiros, então o maior lance mal-sucedido
    # também é.
    consumption: dict[tuple[str, str], int]  # delta_{a,x} — eq. (25)
    remaining_budget: dict[str, int]  # C_a - Delta_a — eq. (27)
    remaining_capacity: dict[str, float]  # W_a - soma dos w_x recebidos — eq. (14)


def _compute_prices(
    *, goods: list[Good], bids: dict[tuple[str, str], int], allocation: Allocation
) -> dict[str, int]:
    """Preço de mercado por bem — eq. (24): maior lance mal-sucedido, ou 1."""
    highest_unsuccessful: dict[str, int] = {}
    for (agent_id, good_id), credits in bids.items():
        if allocation.get((agent_id, good_id), 0) == 0:
            if credits > highest_unsuccessful.get(good_id, 0):
                highest_unsuccessful[good_id] = credits
    return {good.id: highest_unsuccessful.get(good.id, 1) for good in goods}


def _compute_consumption(
    *, bids: dict[tuple[str, str], int], allocation: Allocation, prices: dict[str, int]
) -> dict[tuple[str, str], int]:
    """Consumo de créditos por demanda vencedora — eq. (25)."""
    consumption: dict[tuple[str, str], int] = {}
    for (agent_id, good_id), credits in bids.items():
        if allocation.get((agent_id, good_id), 0):
            price = prices[good_id]
            consumption[(agent_id, good_id)] = price if credits >= price else credits
    return consumption


def run_auction(
    auction_input: AuctionInput, *, resolver: Resolver = "ilp"
) -> AuctionResult:
    """Executa uma rodada de leilão: resolve o WDP e liquida preços/consumo.

    `resolver` escolhe quem decide a alocação — a PLI global do anteprojeto ou
    a varredura gulosa por lance decrescente, que é o mecanismo de *bidding
    points*. É o único ponto em que as duas células do leilão diferem.
    """
    bids = {(b.agent_id, b.good_id): b.credits for b in auction_input.bids}
    initial_capacity = {a.id: a.capacity for a in auction_input.agents}
    if not bids:
        return AuctionResult({}, {}, {}, {}, dict(auction_input.budgets), initial_capacity)

    # Preferências finais: lance + viés + desempate + perturbação — eq. (22)
    rectified_bias = rectify_bias(auction_input.bias)
    epsilon = auction_input.epsilon
    if epsilon is None:
        epsilon = stochastic_perturbations(
            list(bids.keys()),
            num_agents=len(auction_input.agents),
            num_goods=len(auction_input.goods),
            seed=auction_input.seed,
        )

    # A ordem de desempate pode cobrir mais agentes do que os presentes nesta
    # rodada (numa simulação multi-período, alpha é fixo para a população
    # inteira), então alpha_hat é normalizado pelo tamanho da própria ordem.
    default_order = sorted(a.id for a in auction_input.agents)
    ranks: dict[str, dict[str, int]] = {}
    for good in auction_input.goods:
        order = auction_input.tie_break_order.get(good.id) or default_order
        ranks[good.id] = {agent_id: i + 1 for i, agent_id in enumerate(order)}

    demands: list[Demand] = []
    for (agent_id, good_id), credits in bids.items():
        order_ranks = ranks.get(good_id) or {}
        order_size = len(order_ranks) or len(auction_input.agents)
        rank = order_ranks.get(agent_id, order_size)
        alpha_hat = tie_break_factor(rank, order_size)
        beta_hat = rectified_bias.get((agent_id, good_id), 0)
        pref = credits + beta_hat + alpha_hat + epsilon.get((agent_id, good_id), 0.0)
        demands.append(Demand(agent_id, good_id, pref))

    problem = Problem(
        agents=auction_input.agents,
        goods=auction_input.goods,
        demands=demands,
        exclusions=auction_input.exclusions,
    )
    # O resolvedor é o segundo eixo da comparação. Tudo o mais — a preferência
    # da eq. (22), o preço de 2º preço da eq. (24) e o consumo da eq. (27) — é
    # calculado igual nos dois, de modo que a diferença entre as duas células
    # seja só quem decidiu a alocação.
    allocation = (solve_wdp if resolver == "ilp" else solve_wdp_greedy)(problem)

    # Preços de mercado e consumo de créditos — eq. (24)-(26)
    prices = _compute_prices(goods=auction_input.goods, bids=bids, allocation=allocation)
    consumption = _compute_consumption(bids=bids, allocation=allocation, prices=prices)

    weight_by_good = {g.id: g.weight for g in auction_input.goods}
    remaining_budget = dict(auction_input.budgets)
    remaining_capacity = dict(initial_capacity)
    for (agent_id, good_id), consumed in consumption.items():
        remaining_budget[agent_id] -= consumed
        remaining_capacity[agent_id] -= weight_by_good[good_id]

    return AuctionResult(
        bids=bids,
        allocation=allocation,
        prices=prices,
        consumption=consumption,
        remaining_budget=remaining_budget,
        remaining_capacity=remaining_capacity,
    )
