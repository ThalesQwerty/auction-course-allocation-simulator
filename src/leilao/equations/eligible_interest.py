"""O interesse total do que o aluno pode cursar — o denominador da reserva."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def eligible_interest(
    *, interest: Mapping[str, float], eligible: Sequence[str]
) -> float:
    """`interest` e `eligible` são os dois por **disciplina**."""
    return sum(interest.get(discipline, 0.0) for discipline in eligible)
