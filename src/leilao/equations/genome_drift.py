"""Quanto o genoma médio se moveu numa janela de gerações.

    deriva = média_g [ desvio_janela(média do gene g) / escala_g ]

É o estatístico do critério de parada. Com ele e o mesmo número medido no
controle negativo, "convergiu" passa a ter definição operacional: a população
real parou de se mover além do que a deriva sozinha explica.

POR QUE O GENÓTIPO, E NÃO A APTIDÃO
------------------------------------

A aptidão é medida **relativa à própria coorte**, então a aptidão média
relativa é ~0 por construção, sempre. Não existe "parou de melhorar" para
servir de platô: a população pode continuar evoluindo com a média parada.

Amplitude de aptidão também não serve. Com 180 genótipos, a amplitude
esperada *só de ruído* é ~`7,3/√N` — 3,3 com N = 5 observações, e só desce de
1 acima de N ≈ 55. Um limiar abaixo do piso de ruído nunca dispara.

A ESCALA É FIXA
---------------

A normalização por gene é obrigatória: `β_u` varre unidades e `α_u` varre
centésimos, de modo que somar os deslocamentos crus faria a métrica enxergar
só `β_u`.

E a escala tem de ser **fixa** — o espalhamento de cada gene na geração 1 —,
nunca a da geração corrente. Com a corrente, a normalização encolhe junto com
o que se mede, o valor infla e o critério nunca dispara exatamente quando
deveria.

Gene de escala nula (um nível só) não entra na média: ele não tem para onde
derivar, e dividir por zero o faria dominar tudo.

Não está no anteprojeto.
"""
from __future__ import annotations

import statistics
from collections.abc import Sequence


def genome_drift(
    *, window: Sequence[Sequence[float]], scales: Sequence[float]
) -> float:
    if len(window) < 2:
        return float("inf")
    if any(len(row) != len(scales) for row in window):
        raise ValueError("cada ponto da janela precisa de um valor por gene")

    spreads = [
        statistics.pstdev([row[gene] for row in window]) / scales[gene]
        for gene in range(len(scales))
        if scales[gene] > 0.0
    ]
    return sum(spreads) / len(spreads) if spreads else 0.0
