"""Pressão sobre a oferta: candidatos por vaga, disciplina a disciplina."""
from __future__ import annotations

from collections.abc import Sequence

from ._mean import mean


def demand_per_seat(*, demands: Sequence[float]) -> float:
    return mean(demands)
