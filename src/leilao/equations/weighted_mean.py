"""Como uma execução inteira vira um número por métrica.

    valor = Σ_t (métrica_t · alunos_t) / Σ_t alunos_t

A média das métricas de período **ponderada pelos alunos medidos**. A
simulação termina numa fase de drenagem, em que a população só diminui, e uma
média simples daria a um período final de vinte alunos o mesmo peso de um
período cheio de trezentos. Ponderar corrige isso sem recortar o horizonte à
mão.

O peso são os alunos **medidos** (`metrics.students`), não os ativos: o
calouro conta como gente e não como dado, e o primeiro período — em que todo
mundo acabou de ingressar — simplesmente não entra.

`None` quando não há o que promediar. Um zero ali seria um valor medido, e
não a ausência de medida.
"""
from __future__ import annotations

from collections.abc import Sequence


def weighted_mean(pairs: Sequence[tuple[float, int]]) -> float | None:
    total = sum(weight for _, weight in pairs)
    if not total:
        return None
    return sum(value * weight for value, weight in pairs) / total
