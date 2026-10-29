"""Correlação entre CR e satisfação — anteprojeto, eq. (57).

    λ = Σ(x−x̄)(y−ȳ) / √( Σ(x−x̄)² · Σ(y−ȳ)² )

Mede se a alocação segue o histórico. **Descreve, não pontua**: qual lado é
melhor depende de alocar por mérito passado ou por necessidade, e essa é uma
escolha do leitor, não do mecanismo.

Sem variância em algum dos lados o coeficiente não existe, e vale 0 — é o
caso do período em que todo mundo tem CR zero.

O resíduo de ponto flutuante pode passar de 1 em módulo (visto:
−1,0000000000000002), e coeficiente fora de [−1, 1] não é correlação; daí o
corte na saída.
"""
from __future__ import annotations

import math
from collections.abc import Sequence


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    variance_x = sum((x - mean_x) ** 2 for x in xs)
    variance_y = sum((y - mean_y) ** 2 for y in ys)
    if variance_x == 0 or variance_y == 0:
        return 0.0
    return max(-1.0, min(1.0, covariance / math.sqrt(variance_x * variance_y)))
