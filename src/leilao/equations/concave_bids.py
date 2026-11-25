"""A mochila côncava do lance — substitui as eqs. (44)-(46)."""
from __future__ import annotations

import heapq
from collections.abc import Iterable


def concave_bids(
    *,
    scores: dict[str, float],
    available: Iterable[str],
    budget: int,
    reserve: float = 0.0,
) -> dict[str, int]:
    wanted = set(available)
    pool = [name for name in scores if name in wanted and scores[name] > 0.0]
    if not pool or budget <= 0:
        return {}

    rank = {name: index for index, name in enumerate(pool)}
    frontier = [(-scores[name], rank[name], name, 1) for name in pool]
    heapq.heapify(frontier)

    bids: dict[str, int] = {}
    for _ in range(budget):
        gain, _rank, name, credits_here = frontier[0]
        if -gain < reserve:
            break
        heapq.heappop(frontier)
        bids[name] = bids.get(name, 0) + 1
        following = credits_here + 1
        heapq.heappush(frontier, (-scores[name] / following, rank[name], name, following))
    return bids
