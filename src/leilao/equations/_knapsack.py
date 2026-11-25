"""A mochila 0-1 sobre a carga horária, com grafo de conflito opcional."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import gcd


def knapsack(
    *,
    items: Sequence[str],
    values: Mapping[str, float],
    weights: Mapping[str, int],
    capacity: int,
    conflicts: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """O subconjunto, devolvido **na ordem de `items`**."""
    if capacity < 0:
        raise ValueError("a capacidade da mochila não pode ser negativa")

    bit_of_clique: dict[str, int] = {}
    cliques: dict[str, int] = {}
    for name in items:
        mask = 0
        for clique in (conflicts or {}).get(name, ()):
            mask |= bit_of_clique.setdefault(clique, 1 << len(bit_of_clique))
        cliques[name] = mask

    taken = 0
    kept: set[str] = set()
    for name in items:
        if weights[name] <= 0 and not taken & cliques[name]:
            kept.add(name)
            taken |= cliques[name]

    pool = [name for name in items if 0 < weights[name] <= capacity]
    crowded = taken
    for name in pool:
        if crowded & cliques[name]:
            break
        crowded |= cliques[name]
    else:
        if sum(weights[name] for name in pool) <= capacity:
            kept.update(pool)
            return [name for name in items if name in kept]

    unit = 0
    for name in pool:
        unit = gcd(unit, weights[name])
    scaled = {name: weights[name] // unit for name in pool}
    room = capacity // unit

    dp: list[tuple[float, tuple[int, ...], int]] = [
        (0.0, (), taken) for _ in range(room + 1)
    ]
    for index, name in enumerate(pool):
        weight, value, clique = scaled[name], values.get(name, 0.0), cliques[name]
        for c in range(room, weight - 1, -1):
            carried, chosen, occupied = dp[c - weight]
            if occupied & clique:
                continue
            candidate = (carried + value, chosen + (index,), occupied | clique)
            if _wins(candidate, dp[c]):
                dp[c] = candidate

    best = dp[0]
    for cell in dp[1:]:
        if _wins(cell, best):
            best = cell

    kept.update(pool[index] for index in best[1])
    return [name for name in items if name in kept]


def _wins(
    candidate: tuple[float, tuple[int, ...], int],
    current: tuple[float, tuple[int, ...], int],
) -> bool:
    """Mais utilidade vence; empatada, vence o índice mais baixo."""
    return candidate[0] > current[0] or (
        candidate[0] == current[0] and candidate[1] < current[1]
    )
