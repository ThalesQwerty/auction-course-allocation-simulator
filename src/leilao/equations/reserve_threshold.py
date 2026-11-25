"""A utilidade de reserva: a opção externa do aluno contra o que ele pode cursar."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Behavior:
    """O perfil de estratégia: como o aluno traduz utilidade em mensagem."""

    selectivity: float = 0.0


NEUTRAL = Behavior()


def reserve_threshold(*, selectivity: float, interest: float) -> float:
    """`interest` é `Σ_{X ∈ M_a^(t)} I_{a,X}` — o interesse total das"""
    if selectivity <= 0.0 or interest <= 0.0:
        return 0.0
    return selectivity / (selectivity + interest)
