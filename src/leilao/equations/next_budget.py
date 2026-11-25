"""O orçamento do período seguinte — anteprojeto, eqs. (36) e (37)."""
from __future__ import annotations


def next_budget(
    *,
    started_with: int,
    spent: int,
    period_return: int,
    min_credits: int,
    max_credits: int | None = None,
) -> int:
    carried = started_with - spent + period_return
    if max_credits is not None:
        carried = min(carried, max_credits)
    return max(carried, min_credits)
