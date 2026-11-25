"""O que o aluno leva, das vagas que obteve, quando a disponibilidade aperta."""
from __future__ import annotations

from collections.abc import Iterable

from ._knapsack import knapsack


def retained_set(
    *,
    utilities: dict[str, float],
    hours: dict[str, int],
    obtained: Iterable[str],
    load: int,
) -> list[str]:
    if load < 0:
        raise ValueError("a carga efetiva não pode ser negativa")

    wanted = set(obtained)
    ordered = [name for name in utilities if name in wanted]
    ordered += [name for name in sorted(wanted) if name not in utilities]

    ceiling = min(load, sum(hours[name] for name in ordered if hours[name] > 0))
    return knapsack(
        items=ordered, values=utilities, weights=hours, capacity=ceiling
    )
