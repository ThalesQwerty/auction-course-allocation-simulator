"""Créditos efetivamente consumidos por uma demanda vencedora — anteprojeto, eq. (25).
"""
from __future__ import annotations


def consumption(
    *,
    bids: dict[tuple[str, str], int],
    allocation: dict[tuple[str, str], int],
    prices: dict[str, int],
) -> dict[tuple[str, str], int]:
    return {
        (agent_id, good_id): min(credits, prices[good_id])
        for (agent_id, good_id), credits in bids.items()
        if allocation.get((agent_id, good_id), 0)
    }
