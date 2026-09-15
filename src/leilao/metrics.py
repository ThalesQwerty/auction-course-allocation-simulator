"""Métricas de avaliação dos mecanismos de alocação (anteprojeto, Seção 7.3.3).

Cobre satisfação por agente (eq. 51), eficiência agregada (eq. 53), fração de
ocupação das vagas (eq. 54), Índice de Equidade de Jain (eq. 55) e correlação
de Pearson entre desempenho acadêmico e satisfação (eq. 57).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .entities import Allocation, Good


def satisfaction_by_agent(
    *,
    utilities: dict[tuple[str, str], float],
    allocation: Allocation,
) -> dict[str, float]:
    """psi_a = (1/U_a) * sum_x u_{a,x} * z_{a,x}  — eq. (51).

    `utilities` mapeia (agent_id, good_id) -> u_{a,x} para TODAS as demandas
    originais do agente (usadas para compor U_a), não apenas as vencedoras.
    """
    total_utility: dict[str, float] = {}
    weighted_allocation: dict[str, float] = {}

    for (agent_id, good_id), u in utilities.items():
        total_utility[agent_id] = total_utility.get(agent_id, 0.0) + u
        won = allocation.get((agent_id, good_id), 0)
        if won:
            weighted_allocation[agent_id] = weighted_allocation.get(agent_id, 0.0) + u

    return {
        agent_id: (weighted_allocation.get(agent_id, 0.0) / u_a if u_a > 0 else 0.0)
        for agent_id, u_a in total_utility.items()
    }


def average_satisfaction(satisfaction: dict[str, float]) -> float:
    """Eficiência de alocação: satisfação média entre os estudantes — eq. (53)."""
    if not satisfaction:
        return 0.0
    return sum(satisfaction.values()) / len(satisfaction)


def occupation_rate(*, goods: list[Good], allocation: Allocation) -> float:
    """Fração de ocupação das vagas — eq. (54): total alocado / total ofertado."""
    total_quantity = sum(g.quantity for g in goods)
    if total_quantity <= 0:
        return 0.0
    total_allocated = sum(1 for won in allocation.values() if won)
    return total_allocated / total_quantity


def jain_fairness_index(satisfaction: dict[str, float]) -> float:
    """Índice de Equidade de Jain — eq. (55).

    Limite inferior 1/|A| (um único agente concentra tudo), limite superior 1
    (todos os agentes têm satisfação idêntica). Retorna 0 no caso indeterminado
    0/0 (nenhum agente com satisfação, por convenção do anteprojeto).
    """
    values = list(satisfaction.values())
    n = len(values)
    if n == 0:
        return 0.0
    sum_values = sum(values)
    sum_squares = sum(v * v for v in values)
    if sum_squares == 0:
        return 0.0
    return (sum_values**2) / (n * sum_squares)


def academic_satisfaction_correlation(
    *,
    academic_index: dict[str, float],
    satisfaction: dict[str, float],
) -> float:
    """Correlação de Pearson entre CR e satisfação — eq. (57).

    Retorna 0.0 se a amostra tiver menos de 2 agentes ou se um dos vetores
    tiver desvio padrão nulo (correlação indefinida nesses casos).
    """
    common_agents = sorted(set(academic_index) & set(satisfaction))
    if len(common_agents) < 2:
        return 0.0
    x = np.array([academic_index[a] for a in common_agents])
    y = np.array([satisfaction[a] for a in common_agents])
    if np.std(x) == 0 or np.std(y) == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


@dataclass
class MetricsReport:
    """Conjunto de métricas de avaliação para um mecanismo (Seção 7.3.3)."""

    average_satisfaction: float  # psi-bar — eq. (53)
    occupation_rate: float  # theta — eq. (54)
    fairness_index: float  # phi (Jain) — eq. (55)
    academic_correlation: float  # lambda (Pearson) — eq. (57)
    satisfaction_by_agent: dict[str, float]


def build_metrics_report(
    *,
    utilities: dict[tuple[str, str], float],
    allocation: Allocation,
    goods: list[Good],
    academic_index: dict[str, float],
) -> MetricsReport:
    """Calcula o relatório completo de métricas para um mecanismo."""
    satisfaction = satisfaction_by_agent(utilities=utilities, allocation=allocation)
    return MetricsReport(
        average_satisfaction=average_satisfaction(satisfaction),
        occupation_rate=occupation_rate(goods=goods, allocation=allocation),
        fairness_index=jain_fairness_index(satisfaction),
        academic_correlation=academic_satisfaction_correlation(
            academic_index=academic_index, satisfaction=satisfaction
        ),
        satisfaction_by_agent=satisfaction,
    )
