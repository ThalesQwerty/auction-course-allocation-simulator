"""Satisfação do aluno num período — anteprojeto, eq. (51).

    ψ_a = Σ_{x ∈ B} u_{a,x} · z_{a,x}

A fração do **desejo total** do aluno naquele período que foi atendida. O
denominador da eq. (51) é a linha inteira da matriz de utilidades, e ela vale
1 por construção (`utility_row` normaliza sobre a grade), então a divisão some
e ψ é a soma simples das utilidades atendidas.

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


def satisfaction(*, utilities: dict[str, float], allocated: Iterable[str]) -> float:
    return sum(utilities.get(name, 0.0) for name in allocated)
