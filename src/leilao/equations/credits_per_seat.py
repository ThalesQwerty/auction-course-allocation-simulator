"""O preço que uma vaga teria se todo o crédito em mãos fosse gasto.

    crédito por vaga = Σ_{a ∈ recorte} C_a^(t,1) / Σ_{x ∈ B} q_x

Mede a **oferta** de crédito do início do período, antes de qualquer lance —
distinta do que sobrou (`mean_credits`), que é o saldo ao fim.

O denominador é a oferta de **toda a universidade**, mesmo num recorte: o
número vira então a parcela do preço global que aquele grupo sustenta, e a
soma dos grupos reproduz o preço esperado da universidade inteira. É a mesma
convenção da ocupação (eq. 54).

Sem vaga ofertada não há preço, e a função não se aplica — o chamador publica
`None`, que é diferente de zero.
"""
from __future__ import annotations


def credits_per_seat(*, supply: int, total_seats: int) -> float | None:
    if not total_seats:
        return None
    return supply / total_seats
