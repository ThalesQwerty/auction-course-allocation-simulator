"""Carga horária que sobra ao agente depois de uma alocação — anteprojeto, eq. (14)."""
from __future__ import annotations


def remaining_capacity(
    *,
    capacity: dict[str, float],
    allocation: dict[tuple[str, str], int],
    weights: dict[str, float],
) -> dict[str, float]:
    remaining = dict(capacity)
    for (agent_id, good_id), taken in allocation.items():
        if taken and agent_id in remaining:
            remaining[agent_id] -= weights[good_id] * taken
    return remaining
