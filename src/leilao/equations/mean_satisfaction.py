"""Eficiência de um recorte — anteprojeto, eq. (53).

    ψ̄ = (1/|A|) · Σ_{a ∈ A} ψ_a

A média da satisfação sobre os alunos **medidos** do recorte, que não são
todos os ativos: o calouro do período recebeu um pacote fixo e não disputou
nada, então ele conta como gente e não como dado (ver `simulation.reports`).
"""
from __future__ import annotations

from collections.abc import Sequence

from ._mean import mean


def mean_satisfaction(satisfactions: Sequence[float]) -> float:
    return mean(satisfactions)
