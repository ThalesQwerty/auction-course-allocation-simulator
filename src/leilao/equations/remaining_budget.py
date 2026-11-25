"""Saldo de créditos do agente ao fim da rodada — anteprojeto, eq. (27)."""
from __future__ import annotations


def remaining_budget(
    *, budgets: dict[str, int], consumption: dict[tuple[str, str], int]
) -> dict[str, int]:
    remaining = dict(budgets)
    for (agent_id, _good_id), consumed in consumption.items():
        if agent_id in remaining:
            remaining[agent_id] -= consumed
    return remaining
