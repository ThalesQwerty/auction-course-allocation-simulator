"""Altura de cada disciplina na DAG — substitui a senioridade da eq. (38)."""
from __future__ import annotations

from ._induction import induct


def curriculum_heights(unlocks: dict[str, tuple[str, ...]]) -> dict[str, int]:
    return induct(
        unlocks,
        combine=lambda successors: 1 + max(successors, default=-1),
        on_cycle=lambda name: ValueError(
            f"há um ciclo de sucessores envolvendo {name!r}: a disciplina nunca "
            "ficaria elegível"
        ),
    )
