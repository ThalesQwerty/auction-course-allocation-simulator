"""A mochila 0-1, com grafo de conflito opcional, no ótimo provado."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


class KnapsackNotSolvedError(RuntimeError):
    """O solver não provou o ótimo. Como no WDP, a factível não serve."""


def knapsack(
    *,
    items: Sequence[str],
    values: Mapping[str, float],
    weights: Mapping[str, int],
    capacity: int,
    conflicts: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """max Σ u·z, s.a. Σ w·z ≤ W e Σ_{x ∈ clique} z ≤ 1, z binário.

    Sem `conflicts` é a mochila 0-1 clássica; com, é o *knapsack problem with
    conflict graph*, fortemente NP-difícil e sem recorrência pseudo-polinomial
    sobre a capacidade no caso geral (Pferschy e Schauer, 2009). Resolve por
    PLI, no HiGHS. Devolve **na ordem de `items`**.
    """
    if capacity < 0:
        raise ValueError("a capacidade da mochila não pode ser negativa")

    pool = [
        name
        for name in items
        if weights[name] <= capacity and values.get(name, 0.0) > 0.0
    ]
    if not pool:
        return []

    members_of: dict[str, list[int]] = {}
    for index, name in enumerate(pool):
        for clique in (conflicts or {}).get(name, ()):
            members_of.setdefault(clique, []).append(index)
    disputed = [members for members in members_of.values() if len(members) > 1]

    if not disputed and sum(weights[name] for name in pool) <= capacity:
        return [name for name in items if name in set(pool)]

    rows = np.zeros((len(disputed) + 1, len(pool)))
    for row, members in enumerate(disputed):
        rows[row, members] = 1.0
    rows[-1] = [weights[name] for name in pool]
    limits = [1.0] * len(disputed) + [float(capacity)]

    answer = milp(
        c=[-values[name] for name in pool],
        constraints=LinearConstraint(rows, -np.inf, limits),
        integrality=np.ones(len(pool)),
        bounds=Bounds(0, 1),
        options={"mip_rel_gap": 0.0},
    )
    if answer.status != 0:
        raise KnapsackNotSolvedError(
            f"mochila de {len(pool)} itens não resolvida: {answer.message}"
        )

    taken = {name for name, z in zip(pool, answer.x) if z > 0.5}
    return [name for name in items if name in taken]
