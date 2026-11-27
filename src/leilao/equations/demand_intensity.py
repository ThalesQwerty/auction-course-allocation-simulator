"""A intensidade de demanda: quanto da oferta elegível o aluno pediu."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

__all__ = ["demand_counts", "demand_intensity"]


def demand_counts(
    *,
    eligible: Iterable[str],
    requested: Iterable[str],
    groups: Mapping[str, str],
    seats: Mapping[str, int],
) -> tuple[int, int]:
    """|M̊| e |M̃|, dobrando turma em disciplina e exigindo turma ofertada."""
    offered = {
        groups.get(name, name)
        for name in eligible
        if seats.get(name, 0) > 0
    }
    asked = {groups.get(name, name) for name in requested} & offered
    return len(offered), len(asked)


def demand_intensity(*, eligible: int, requested: int) -> float | None:
    """δ = |M̃| / |M̊| — ver `Monografia.tex`, eq. (intensidade-demanda)."""
    if eligible <= 0:
        return None
    return requested / eligible
