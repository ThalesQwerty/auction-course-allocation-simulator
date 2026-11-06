"""O melhor resultado possível de um aluno num período — o `U_a` da eq. (43).

    alcançável = Σ_d max_{t ∈ d} ũ_t

A soma, sobre as disciplinas, da utilidade da **turma mais útil** de cada uma.
É o denominador de ψ (`equations.satisfaction`).

POR QUE O MÁXIMO, E POR QUE ELE É ≤ 1
--------------------------------------

Porque o aluno só pode levar **uma** turma por disciplina: as outras estão na
linha e somam para o 1 da normalização, mas não são alcançáveis junto com a
primeira. A desigualdade não é folga nem erro de normalização — é a exclusão
mútua (eq. 5) aparecendo na aritmética.

Com o denominador no 1 da linha inteira, ψ ganharia teto de ~1/k: um aluno que
levasse a melhor turma de **toda** disciplina elegível pararia perto de 0,15
numa grade de 9 turmas. Atingir 1 seria impossível por construção, e não por
escassez.

A soma é **conservada pela redistribuição**: a disciplina travada entrega
`max_t ũ_t`, e a parcela entra inteira em cada turma do alvo, de modo que o
máximo do alvo sobe exatamente nela. Então este número é o mesmo antes e
depois de `equations.utility`, e vale o mesmo em todo período — é denominador
fixo por linha, não móvel.

Sem turmas (uma por disciplina) ele é a soma da linha elegível, que vale 1, e
a divisão some: ψ volta a ser a soma simples das utilidades atendidas.

Não está no anteprojeto, que é de turma única: lá a eq. (43) é a soma direta.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def reachable_utility(
    *,
    utilities: Mapping[str, float],
    classes: Mapping[str, Sequence[str]] | None = None,
) -> float:
    if not classes:
        return sum(utilities.values())
    return sum(
        max((utilities.get(name, 0.0) for name in names), default=0.0)
        for names in classes.values()
    )
