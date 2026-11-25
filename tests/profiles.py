"""Distribuições de população para os testes."""
from __future__ import annotations

from leilao.config import AvailabilityShape, default_availability


def always_available(max_hours: int) -> AvailabilityShape:
    """A distribuição que praticamente nunca exclui."""
    return AvailabilityShape(mode_hours=max_hours - 1, full_load_rate=0.9999)


def single_axis(max_hours: int) -> dict:
    """Os eixos da população num cenário de teste."""
    return {
        "availability": default_availability(max_hours),
        "selectivity_median": 0.0,
        "grade_cuts": (),
        "reserve_cuts": (),
    }
