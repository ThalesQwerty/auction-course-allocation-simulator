"""Período de cada disciplina na grade, induzido dos pré-requisitos.

    p_x = 1                               se ninguém desbloqueia x
    p_x = 1 + max_{y ∈ requires(x)} p_y   caso contrário

O período **não se configura**: ele sai da cadeia. Quem não exige nada é 1º
período; quem exige é o período seguinte ao mais tardio dos pré-requisitos.

É a mesma recorrência da altura sobre a aresta oposta, e conta do outro
extremo: a altura olha para frente (quanto curso depende desta disciplina), o
período olha para trás (quanto curso ela exige). Serve aos gráficos e à
leitura da grade; a matrícula garantida é a flag `entry`, não este número.
"""
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
