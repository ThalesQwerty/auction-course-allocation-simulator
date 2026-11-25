"""A matriz de perturbações que garante solução ótima única (Seção 7.1.2)."""
from __future__ import annotations

import numpy as np

GRID_DENSITY = 4


def stochastic_perturbations(
    keys: list[tuple[str, str]], *, num_agents: int, num_goods: int, seed: int
) -> dict[tuple[str, str], float]:
    if not keys:
        return {}
    upper_bound = 1.0 / (num_agents**2 * max(num_goods, 1))
    rng = np.random.default_rng(seed)
    grid = np.linspace(
        upper_bound / (len(keys) + 1),
        upper_bound,
        num=len(keys) * GRID_DENSITY,
        endpoint=False,
    )
    chosen = rng.choice(grid, size=len(keys), replace=False)
    rng.shuffle(chosen)
    return {key: float(value) for key, value in zip(keys, chosen)}


def per_agent(perturbations: dict[tuple[str, str], float]) -> dict[str, float]:
    """Um ε por **agente**, para quem prioriza o agente e não o par."""
    smallest: dict[str, str] = {}
    for agent_id, good_id in perturbations:
        if agent_id not in smallest or good_id < smallest[agent_id]:
            smallest[agent_id] = good_id
    return {
        agent_id: perturbations[(agent_id, good_id)]
        for agent_id, good_id in smallest.items()
    }
