"""Taxa de ocupação — anteprojeto, eq. (54).

    θ = vagas alocadas / vagas ofertadas

Num recorte, o denominador continua sendo a oferta de **toda a universidade**:
θ vira então a fração das vagas que foi para aquele grupo, e a soma dos
grupos reproduz a ocupação global. É a mesma convenção de `credits_per_seat`.

Sem oferta não há razão, e o valor é 0.
"""
from __future__ import annotations


def occupancy(*, allocated: int, total_seats: int) -> float:
    return allocated / total_seats if total_seats else 0.0
