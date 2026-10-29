"""Altura de cada disciplina na DAG — substitui a senioridade da eq. (38).

    s_x = 0                         se x não desbloqueia nada
    s_x = 1 + max_{y ∈ unlocks(x)} s_y   caso contrário

O comprimento da cadeia mais longa **à frente** da disciplina: quanto curso
ainda depende dela. É o que entra na invariante de preferência de
`utility_row` — `s_x > s_y ⇒ u_x > u_y` —, de modo que a disciplina que
destrava mais curso vale sempre mais que a terminal, qualquer que tenha sido o
sorteio.

Não se confunde com o **alcance** (`curriculum_reach`), que conta *quantas*
disciplinas ficam destravadas: uma pode ter altura 1 e alcance 10 se destrava
dez terminais de uma vez. Nem com o **período** (`curriculum_period`), que
conta do outro extremo da mesma DAG.
"""
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
