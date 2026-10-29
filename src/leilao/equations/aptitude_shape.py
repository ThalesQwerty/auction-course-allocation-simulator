"""Os parâmetros de forma da Beta da aptidão, a partir de média e concentração.

    forma₁ = média · concentração
    forma₂ = (1 − média) · concentração

A Beta não tem locação nem escala — o suporte é fixo em (0, 1) —, de modo que
os dois números que ela pede são forma pura, e forma pura não se lê: ninguém
olha `(4, 2)` e enxerga "média 0,67, moderadamente espalhada". A interface
edita as duas grandezas que *se* leem, e a conversão acontece aqui, na entrada
do modelo.

As duas respondem perguntas independentes, e as duas importam. A **média**
calibra o cenário contra a taxa de aprovação — é ela que decide se a
universidade forma 30% ou 80%. A **concentração** diz quão apertada a
população fica em torno dela: mesma média com concentração maior é uma
população mais homogênea, e homogeneidade demais apaga a ordenação por CR,
que precisa de dispersão para ter o que ordenar.
"""
from __future__ import annotations


def beta_shape(*, mean: float, concentration: float) -> tuple[float, float]:
    if not 0.0 < mean < 1.0:
        raise ValueError("a média da aptidão deve estar em (0, 1)")
    if concentration <= 0.0:
        raise ValueError("a concentração da aptidão deve ser > 0")
    return mean * concentration, (1.0 - mean) * concentration
