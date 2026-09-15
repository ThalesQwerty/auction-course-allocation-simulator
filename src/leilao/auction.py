"""Mecanismo de leilão por créditos (anteprojeto, Seção 7.1).

Cada rodada de alocação resolve uma instância do problema central P, na qual
as preferências p_{a,x} usadas pelo resolvedor de PLI (wdp_solver.solve_wdp)
são derivadas dos lances em créditos somados ao desempate, viés administrativo
e perturbação estocástica (eq. 22). Após a resolução, calculam-se os preços de
limpeza de mercado (eq. 24) e o consumo de créditos de cada agente (eq. 25-27).

Este módulo cobre a tupla de leilão L = (C^(1), R, R_c, alpha, beta, epsilon)
(eq. 30) para uma sequência de rodadas dentro de um único período de alocação
(Seção 3.2). A camada temporal multi-período da universidade (entrada de
alunos, notas, retorno de créditos — Seção 7.2) é construída por cima deste
módulo e ainda não está implementada nesta versão.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .entities import Agent, Allocation, Demand, Good, MutualExclusion, Problem
from .tie_breaking import rectify_bias, stochastic_perturbations, tie_break_factor
from .wdp_solver import solve_wdp


@dataclass(frozen=True)
class AuctionAgent:
    id: str
    capacity: float  # W_a^(1) — eq. (4)
    budget: int  # C_a^(1) — eq. (19)


@dataclass(frozen=True)
class AuctionGood:
    id: str
    quantity: int  # q_x^(1) — eq. (3)
    weight: float  # w_x — eq. (4)


@dataclass(frozen=True)
class AuctionDemand:
    agent_id: str
    good_id: str
    utility: float  # u_{a,x} in [0, 1] — eq. (41)/(42), guia a estratégia de lance


@dataclass
class AuctionConfig:
    """Insumos de um leilão: tupla L = (C^(1), R, R_c, alpha, beta, epsilon) simplificada.

    `tie_break_order` mapeia good_id -> lista de agent_id em ordem de
    prioridade de desempate (matriz alpha, eq. 20). Se omitido para um bem,
    usa-se a ordem lexicográfica dos ids como padrão determinístico.

    `bias` mapeia (agent_id, good_id) -> viés bruto beta_{a,x} (eq. 21). Pares
    ausentes são tratados como 0 (sem viés).
    """

    agents: list[AuctionAgent]
    goods: list[AuctionGood]
    demands: list[AuctionDemand]
    exclusions: list[MutualExclusion] = field(default_factory=list)
    num_rounds: int = 1
    tie_break_order: dict[str, list[str]] = field(default_factory=dict)
    bias: dict[tuple[str, str], int] = field(default_factory=dict)
    seed: int = 0


@dataclass
class RoundResult:
    round_index: int
    bids: dict[tuple[str, str], int]
    allocation: Allocation
    prices: dict[str, float]
    consumption: dict[tuple[str, str], float]


@dataclass
class AuctionResult:
    rounds: list[RoundResult]
    final_allocation: Allocation  # z^(*) — eq. (16)
    final_consumption: dict[tuple[str, str], float]  # delta^(*) — eq. (28)
    remaining_budget: dict[str, float]  # C_a após a última rodada


def _proportional_bids(
    *,
    agent_budget: int,
    total_utility: float,
    available: list[AuctionDemand],
) -> dict[str, int]:
    """Lances proporcionais à utilidade percebida — eq. (44)-(46).

    `total_utility` é U_a (eq. 42): a soma de utilidades do agente sobre o
    conjunto ORIGINAL de demandas do leilão (fixa por toda a duração do
    leilão), não apenas sobre os bens ainda disponíveis nesta rodada — isso
    preserva a semântica de que o agente reserva a fração (1 - U_a) do
    orçamento e não a gasta neste período.
    """
    if not available or agent_budget <= 0 or total_utility <= 0:
        return {}

    sum_available_utility = sum(d.utility for d in available)
    if sum_available_utility <= 0:
        return {}

    # eq. (44): lances preliminares truncados
    preliminary: dict[str, int] = {
        d.good_id: math.floor(
            agent_budget * total_utility * (d.utility / sum_available_utility)
        )
        for d in available
    }

    # eq. (45): crédito remanescente do truncamento
    remainder = math.floor(agent_budget * total_utility) - sum(preliminary.values())
    if remainder <= 0:
        return {k: v for k, v in preliminary.items() if v > 0}

    # eq. (46): distribui o remanescente em ordem decrescente de utilidade
    ordered_goods = sorted(
        (d.good_id for d in available), key=lambda g: next(
            d.utility for d in available if d.good_id == g
        ), reverse=True,
    )
    final_bids = dict(preliminary)
    for i, good_id in enumerate(ordered_goods):
        if i >= remainder:
            break
        final_bids[good_id] = final_bids.get(good_id, 0) + 1

    return {k: v for k, v in final_bids.items() if v > 0}


def _compute_prices(
    *,
    goods: list[AuctionGood],
    bids: dict[tuple[str, str], int],
    allocation: Allocation,
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
    *,
    bids: dict[tuple[str, str], int],
    allocation: Allocation,
    prices: dict[str, float],
) -> dict[tuple[str, str], float]:
    """Consumo de créditos por demanda vencedora — eq. (25)."""
    consumption: dict[tuple[str, str], float] = {}
    for (agent_id, good_id), credits in bids.items():
        won = allocation.get((agent_id, good_id), 0)
        if won:
            price = prices[good_id]
            consumption[(agent_id, good_id)] = price if credits >= price else float(credits)
    return consumption


def run_auction_round(
    *,
    agents: list[AuctionAgent],
    goods: list[AuctionGood],
    candidate_demands: list[AuctionDemand],
    total_utility_by_agent: dict[str, float],
    exclusions: list[MutualExclusion],
    tie_break_order: dict[str, list[str]],
    bias: dict[tuple[str, str], int],
    seed: int,
    round_index: int,
) -> RoundResult:
    """Executa uma única rodada de leilão sobre o estado atual (agentes/bens)."""
    # 1) Lances proporcionais à utilidade — eq. (44)-(46)
    bids: dict[tuple[str, str], int] = {}
    demands_by_agent: dict[str, list[AuctionDemand]] = {}
    for d in candidate_demands:
        demands_by_agent.setdefault(d.agent_id, []).append(d)

    agent_budget = {a.id: a.budget for a in agents}
    for agent_id, available in demands_by_agent.items():
        agent_bids = _proportional_bids(
            agent_budget=agent_budget.get(agent_id, 0),
            total_utility=total_utility_by_agent.get(agent_id, 0.0),
            available=available,
        )
        for good_id, credits in agent_bids.items():
            bids[(agent_id, good_id)] = credits

    if not bids:
        return RoundResult(round_index, {}, {}, {}, {})

    # 2) Preferências finais: lance + viés + desempate + perturbação — eq. (22)
    rectified_bias = rectify_bias(bias)
    epsilon = stochastic_perturbations(
        list(bids.keys()),
        num_agents=len(agents),
        num_goods=len(goods),
        seed=seed + round_index,
    )

    demands_for_solver: list[Demand] = []
    for (agent_id, good_id), credits in bids.items():
        order = tie_break_order.get(good_id) or sorted(a.id for a in agents)
        rank = order.index(agent_id) + 1 if agent_id in order else len(order)
        alpha_hat = tie_break_factor(rank, len(agents))
        beta_hat = rectified_bias.get((agent_id, good_id), 0)
        pref = credits + beta_hat + alpha_hat + epsilon.get((agent_id, good_id), 0.0)
        demands_for_solver.append(Demand(agent_id, good_id, pref))

    problem = Problem(
        agents=[Agent(a.id, a.capacity) for a in agents],
        goods=[Good(g.id, g.quantity, g.weight) for g in goods],
        demands=demands_for_solver,
        exclusions=exclusions,
    )
    allocation = solve_wdp(problem)

    # 3) Preços de mercado e consumo de créditos — eq. (24)-(26)
    prices = _compute_prices(goods=goods, bids=bids, allocation=allocation)
    consumption = _compute_consumption(bids=bids, allocation=allocation, prices=prices)

    return RoundResult(round_index, bids, allocation, prices, consumption)


def run_auction(config: AuctionConfig) -> AuctionResult:
    """Executa o leilão completo por `config.num_rounds` rodadas (Seção 3.2)."""
    agents = {a.id: a for a in config.agents}
    goods = {g.id: g for g in config.goods}

    total_utility_by_agent: dict[str, float] = {}
    for d in config.demands:
        total_utility_by_agent[d.agent_id] = total_utility_by_agent.get(d.agent_id, 0.0) + d.utility

    remaining_demands = list(config.demands)
    remaining_budget = {a.id: a.budget for a in agents.values()}
    remaining_capacity = {a.id: a.capacity for a in agents.values()}
    remaining_quantity = {g.id: g.quantity for g in goods.values()}

    rounds: list[RoundResult] = []
    final_allocation: Allocation = {}
    final_consumption: dict[tuple[str, str], float] = {}

    for round_index in range(1, config.num_rounds + 1):
        # eq. (15): agente não pode demandar novamente bem já recebido
        candidate = [
            d
            for d in remaining_demands
            if remaining_quantity.get(d.good_id, 0) > 0
        ]
        current_agents = [
            AuctionAgent(a.id, remaining_capacity[a.id], remaining_budget[a.id])
            for a in agents.values()
        ]
        current_goods = [
            AuctionGood(g.id, remaining_quantity[g.id], g.weight) for g in goods.values()
        ]

        result = run_auction_round(
            agents=current_agents,
            goods=current_goods,
            candidate_demands=candidate,
            total_utility_by_agent=total_utility_by_agent,
            exclusions=config.exclusions,
            tie_break_order=config.tie_break_order,
            bias=config.bias,
            seed=config.seed,
            round_index=round_index,
        )
        rounds.append(result)

        # eq. (16): agregação da alocação final
        for key, won in result.allocation.items():
            if won:
                final_allocation[key] = 1

        # eq. (27): desconta consumo do orçamento do agente
        weight_by_good = {g.id: g.weight for g in goods.values()}
        for (agent_id, good_id), consumed in result.consumption.items():
            remaining_budget[agent_id] -= consumed
            final_consumption[(agent_id, good_id)] = (
                final_consumption.get((agent_id, good_id), 0.0) + consumed
            )
            # eq. (14): desconta a carga horária recebida da capacidade
            remaining_capacity[agent_id] -= weight_by_good[good_id]
            # eq. (13): desconta a unidade alocada da disponibilidade do bem
            remaining_quantity[good_id] -= 1

        # eq. (15): remove do conjunto de demandas remanescentes os bens já vencidos
        won_pairs = {k for k, v in result.allocation.items() if v}
        remaining_demands = [
            d for d in remaining_demands if (d.agent_id, d.good_id) not in won_pairs
        ]

        if not candidate:
            break

    return AuctionResult(
        rounds=rounds,
        final_allocation=final_allocation,
        final_consumption=final_consumption,
        remaining_budget=remaining_budget,
    )
