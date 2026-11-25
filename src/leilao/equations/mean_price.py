"""O preço do período de uma disciplina."""
from __future__ import annotations


def mean_price(*, price_sum: int, rounds_on_market: int) -> float | None:
    if not rounds_on_market:
        return None
    return price_sum / rounds_on_market
