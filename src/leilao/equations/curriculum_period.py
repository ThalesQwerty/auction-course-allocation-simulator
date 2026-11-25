"""Período de cada disciplina na grade, induzido dos pré-requisitos."""
from __future__ import annotations

from ._induction import induct


def curriculum_periods(prerequisites: dict[str, tuple[str, ...]]) -> dict[str, int]:
    return induct(
        prerequisites,
        combine=lambda predecessors: 1 + max(predecessors, default=0),
        on_cycle=lambda name: ValueError(
            f"há um ciclo de sucessores envolvendo {name!r}: a disciplina nunca "
            "ficaria elegível"
        ),
    )
