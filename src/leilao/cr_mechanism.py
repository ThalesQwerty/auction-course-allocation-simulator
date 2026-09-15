"""Mecanismo tradicional por Coeficiente de Rendimento (CR) — linha de base (Seção 7.3.1).

Ao contrário do leilão, aqui as restrições de carga horária e choque de
horário são resolvidas LOCALMENTE por cada estudante, ex-ante, como uma
otimização de mochila 0-1 com grafo de conflito (eq. 50) — usando a mesma
utilidade percebida u_{a,x} como valor e a carga horária w_x como peso. As
vagas são então distribuídas globalmente por ordenação decrescente de
prioridade N_a + epsilon (eq. 49), sem replanejamento entre estudantes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .entities import Agent, Allocation, Demand, Good, MutualExclusion, Problem
from .tie_breaking import stochastic_perturbations
from .wdp_solver import solve_wdp


@dataclass(frozen=True)
class CRAgent:
    id: str
    capacity: float  # W_a
    academic_index: float  # N_a (CR) — eq. (49)


@dataclass(frozen=True)
class CRGood:
    id: str
    quantity: int
    weight: float


@dataclass(frozen=True)
class CRDemandCandidate:
    agent_id: str
    good_id: str
    utility: float  # u_{a,x} in [0, 1] — eq. (41)


@dataclass
class CRConfig:
    agents: list[CRAgent]
    goods: list[CRGood]
    demands: list[CRDemandCandidate]
    exclusions: list[MutualExclusion] = field(default_factory=list)
    seed: int = 0


@dataclass
class CRResult:
    requested: Allocation  # D^(t): solicitações decididas localmente por cada aluno
    allocation: Allocation  # z: resultado da alocação global por prioridade de CR
    priority: dict[tuple[str, str], float]  # N_a + epsilon_{a,x}


def _select_local_demands(
    agent: CRAgent,
    candidates: list[CRDemandCandidate],
    goods_by_id: dict[str, CRGood],
    exclusions: list[MutualExclusion],
) -> set[str]:
    """Mochila 0-1 local do estudante com grafo de conflito — eq. (50).

    O estudante otimiza localmente sua própria utilidade sujeito à fração
    U_a de sua carga horária máxima (aqui, U_a = soma das utilidades
    percebidas, respeitando 0 < U_a <= 1 por construção — eq. 43) e às
    exclusões mútuas de choque de horário.
    """
    if not candidates:
        return set()

    total_utility = min(1.0, sum(c.utility for c in candidates))
    if total_utility <= 0:
        return set()

    mini_problem = Problem(
        agents=[Agent(agent.id, total_utility * agent.capacity)],
        goods=[
            Good(gid, g.quantity if g.quantity > 0 else 1, g.weight)
            for gid, g in goods_by_id.items()
            if gid in {c.good_id for c in candidates}
        ],
        demands=[Demand(agent.id, c.good_id, c.utility) for c in candidates],
        exclusions=exclusions,
    )
    allocation = solve_wdp(mini_problem)
    return {good_id for (_, good_id), won in allocation.items() if won}


def run_cr_allocation(config: CRConfig) -> CRResult:
    """Executa uma rodada do mecanismo tradicional por CR (Seção 7.3.1)."""
    goods_by_id = {g.id: g for g in config.goods}
    agents_by_id = {a.id: a for a in config.agents}

    demands_by_agent: dict[str, list[CRDemandCandidate]] = {}
    for d in config.demands:
        demands_by_agent.setdefault(d.agent_id, []).append(d)

    # 1) Cada estudante decide localmente suas solicitações — eq. (50)
    requested: Allocation = {}
    for agent_id, candidates in demands_by_agent.items():
        agent = agents_by_id[agent_id]
        chosen_goods = _select_local_demands(agent, candidates, goods_by_id, config.exclusions)
        for good_id in chosen_goods:
            requested[(agent_id, good_id)] = 1

    if not requested:
        return CRResult(requested={}, allocation={}, priority={})

    # 2) Prioridade global: N_a + epsilon_{a,x} — eq. (49)
    epsilon = stochastic_perturbations(
        list(requested.keys()),
        num_agents=len(config.agents),
        num_goods=len(config.goods),
        seed=config.seed,
    )
    priority = {
        key: agents_by_id[key[0]].academic_index + epsilon.get(key, 0.0)
        for key in requested
    }

    # 3) Ordenação decrescente + alocação gulosa respeitando a disponibilidade
    remaining_quantity = {g.id: g.quantity for g in config.goods}
    allocation: Allocation = {}
    for key in sorted(requested, key=lambda k: priority[k], reverse=True):
        agent_id, good_id = key
        if remaining_quantity.get(good_id, 0) > 0:
            allocation[key] = 1
            remaining_quantity[good_id] -= 1
        else:
            allocation[key] = 0

    return CRResult(requested=requested, allocation=allocation, priority=priority)
