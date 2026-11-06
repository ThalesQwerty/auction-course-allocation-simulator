"""Satisfação do aluno num período — anteprojeto, eq. (51).

    ψ_a = Σ_{x ∈ B} u_{a,x} · z_{a,x}

A fração do **desejo alcançável** do aluno naquele período que foi
atendida. O denominador é `equations.reachable_utility` — a soma, sobre as
disciplinas, da utilidade da turma mais útil de cada uma —, porque o aluno
só pode levar uma turma por disciplina. É utilidade, e não interesse,
porque disciplina que ele não podia cursar não é desejo atendível.

**Sem turmas o denominador vale 1** e a divisão some: o interesse é
normalizado sobre a grade (`interest_row`) e a redistribuição o conserva
(`utility`), de modo que ψ volta a ser a soma simples das utilidades
atendidas, como era antes de as turmas existirem.

**O denominador mudou**, e vale saber qual leitura você está olhando. Antes
era `U_a` — a soma só sobre o conjunto elegível (eq. 43) —, e ψ media "do que
eu podia cursar, quanto cursei". Como U_a varia de ~0,002 a ~0,65 entre
linhas, aquilo era uma razão de denominador móvel: maximizá-la premiava estar
num período pobre de opções. As duas leituras se recuperam uma da outra por
`ψ_elegível = ψ / U_a`. O que se perde com o denominador fixo é que **ψ = 1
deixa de ser atingível** — exigiria cursar a grade inteira num período —, e o
que se ganha é uma escala igual para todo aluno, em todo período.

`allocated` pode trazer disciplina fora de `utilities` (já aprovada, por
exemplo); ela é ignorada, que é o certo — não é desejo deste período.
"""
from __future__ import annotations

from collections.abc import Iterable


def satisfaction(
    *,
    utilities: dict[str, float],
    allocated: Iterable[str],
    reachable: float = 1.0,
) -> float:
    if reachable <= 0.0:
        return 0.0
    return sum(utilities.get(name, 0.0) for name in allocated) / reachable
