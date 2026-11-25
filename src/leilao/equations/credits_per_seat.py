"""O preço que uma vaga teria se todo o crédito em mãos fosse gasto."""
from __future__ import annotations


def credits_per_seat(*, supply: int, total_seats: int) -> float | None:
    if not total_seats:
        return None
    return supply / total_seats
