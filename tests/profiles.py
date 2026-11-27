"""Distribuições de população para os testes."""
from __future__ import annotations

from leilao.config import AvailabilityShape, default_availability


SEM_SELETIVIDADE = -50.0
"""O especulador: S tão pequeno que a reserva some nos decimais."""


def always_available(max_hours: int) -> AvailabilityShape:
    """A distribuição que praticamente nunca exclui."""
    return AvailabilityShape(
        hours_sd=max(0.1, round(max_hours * 0.05, 1)), full_load_rate=0.9999
    )


def single_axis(max_hours: int) -> dict:
    """Os eixos da população num cenário de teste."""
    return {
        "availability": default_availability(max_hours),
        "selectivity_mean": SEM_SELETIVIDADE,
        "grade_cuts": (),
        "demand_cuts": (),
    }
