"""Desperdício de vaga: quanto do que foi alocado não chegou a ser cursado."""
from __future__ import annotations


def exclusion_rate(*, excluded: int, allocated: int) -> float:
    if excluded < 0 or allocated < 0:
        raise ValueError("as contagens de vagas não podem ser negativas")
    if excluded > allocated:
        raise ValueError("não se pode excluir mais vagas do que se obteve")
    return excluded / allocated if allocated else 0.0
