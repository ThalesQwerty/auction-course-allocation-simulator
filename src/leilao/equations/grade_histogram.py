"""Como as notas de primeira tentativa se distribuem.

    faixa(n) = min(bins − 1, ⌊ n/10 · bins ⌋)
    altura_i = contagem_i / total

Faixas de mesma largura sobre [0, 10], e a saída é a fração em cada uma,
somando 1. São **dez**, as mesmas das utilidades, de modo que os dois
gráficos se leiam do mesmo jeito; aqui elas também caem bem na escala, porque
as divisas são 0, 1, 2 … 10, que é como se lê uma nota.

O corte em `bins − 1` fecha a última faixa dos dois lados: a nota 10 cai nela
em vez de cair numa faixa a mais. É por isso que o 10 conta como aprovação e
não some do gráfico.

Recebe as notas **já calculadas**, e não o sorteio cru: com a nota saindo de
uma potência da aptidão, não há mais "valor cru" que se leia como nota. O que
o gráfico mostra é o que a fórmula de fato produz.
"""
from __future__ import annotations

from collections.abc import Sequence

BINS = 10
TOP = 10.0


def grade_histogram(grades: Sequence[float], bins: int = BINS) -> list[float]:
    if not grades:
        return [0.0] * bins
    counts = [0] * bins
    for grade in grades:
        counts[min(bins - 1, max(0, int(grade / TOP * bins)))] += 1
    return [count / len(grades) for count in counts]
