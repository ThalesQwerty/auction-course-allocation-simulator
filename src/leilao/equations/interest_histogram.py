"""Como o interesse se reparte dentro da linha de um aluno.

    faixa(u) = min(bins − 1, ⌊ (u − min_linha)/(max_linha − min_linha) · bins ⌋)
    altura_i = contagem_i / total

Cada linha (aluno, período) é reescalada ao **próprio** [mínimo, máximo] e
dividida em faixas de mesma largura; a saída é a fração de valores em cada
faixa, somando 1. Valor zero não entra — não é preferência fraca, e o sorteio
não o produz (`behavior.UNDERFLOW_GUARD`).

É **relatório, não decisão**: lê o interesse cru, antes de o histórico do
aluno o converter em utilidade, porque é o interesse que σ e a atratividade
governam.

**A escala é por linha, e não global, porque global degenera.** Com a faixa
tomada do menor ao maior valor da matriz inteira, um único extremo define o
intervalo e, de σ = 1 em diante, 94% dos valores caem na primeira faixa:
todos os gráficos saem iguais e nenhum descreve um aluno. Por linha, a
leitura é "como *um* aluno reparte a preferência dele", que é a grandeza que
σ controla — e aí a forma de fato muda quando σ muda.

A última faixa guarda sempre o máximo da linha, então ela nunca é vazia: num
conjunto de n disciplinas ela vale pelo menos 1/n. Linha com menos de dois
valores positivos não tem o que repartir e é descartada.
"""
from __future__ import annotations

from collections.abc import Iterable

BINS = 10


def interest_histogram(
    rows: Iterable[dict[str, float]], bins: int = BINS
) -> list[float]:
    counts = [0] * bins
    total = 0
    for row in rows:
        values = [value for value in row.values() if value > 0]
        if len(values) < 2:
            continue
        low, high = min(values), max(values)
        span = high - low
        for value in values:
            index = (
                bins - 1 if span <= 0 else min(bins - 1, int((value - low) / span * bins))
            )
            counts[index] += 1
        total += len(values)
    if not total:
        return [0.0] * bins
    return [count / total for count in counts]
