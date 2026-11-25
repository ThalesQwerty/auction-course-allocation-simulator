"""Preço de mercado de cada bem, a segundo preço — anteprojeto, eq. (24)."""
from __future__ import annotations


FLOOR = 1


def market_prices(
    *,
    good_ids: list[str],
    bids: dict[tuple[str, str], int],
    allocation: dict[tuple[str, str], int],
) -> dict[str, int]:
    highest_loser: dict[str, int] = {}
    for (agent_id, good_id), credits in bids.items():
        if allocation.get((agent_id, good_id)):
            continue
        highest_loser[good_id] = max(highest_loser.get(good_id, 0), credits)
    return {good_id: highest_loser.get(good_id, FLOOR) for good_id in good_ids}
