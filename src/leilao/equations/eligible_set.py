"""O conjunto elegível do aluno no período — anteprojeto, eq. (42).

    elegível = { x : x ∉ aprovadas
                   ∧ pré-requisitos(x) ⊆ aprovadas
                   ∧ ¬(x é optativa ∧ exigência X já cumprida) }

Fora dele a utilidade é zero, e é o zero que marca o inelegível — as duas
mochilas filtram por `utilidade > 0`.

**O teto nas optativas** não é calibragem, é o que faz X significar alguma
coisa. Sem ele a optativa fica elegível para sempre (nunca aprovada, sem
pré-requisito), o aluno continua apostando nela por utilidade, e medindo-se o
cenário quem conclui tinha aprovado o catálogo inteiro — 1 560 h de optativa
onde 480 h eram exigidas. A exigência não restringia nada, e a
substituibilidade nunca chegava a ser exercida.

Com `X = 0` nenhuma optativa é elegível, que é a leitura consistente: sem
exigência, elas não contam para nada.

A **ordem da saída** é a da grade no cenário, e é carga: é dela que as duas
mochilas tiram o desempate entre disciplinas de mesma utilidade.
"""
from __future__ import annotations

from collections.abc import Sequence, Set


def eligible_set(
    *,
    names: Sequence[str],
    approved: Set[str],
    prerequisites: dict[str, tuple[str, ...]],
    elective_hours_by_discipline: dict[str, int],
    elective_hours_needed: int,
) -> list[str]:
    earned = sum(
        hours
        for name, hours in elective_hours_by_discipline.items()
        if name in approved
    )
    quota_met = earned >= elective_hours_needed
    return [
        name
        for name in names
        if name not in approved
        and all(p in approved for p in prerequisites[name])
        and not (name in elective_hours_by_discipline and quota_met)
    ]
