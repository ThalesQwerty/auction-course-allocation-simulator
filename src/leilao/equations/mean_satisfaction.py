"""ψ̄ — a satisfação média de um recorte; anteprojeto, eq. (53)."""
from __future__ import annotations

from collections.abc import Sequence

from ._mean import mean


def mean_satisfaction(satisfactions: Sequence[float]) -> float:
    return mean(satisfactions)
