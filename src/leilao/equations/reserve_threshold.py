"""O limiar da reserva: a seletividade em múltiplos do score médio.

    limiar = seletividade · (Σ_x score_x) / |scores|

A **seletividade** é a outra metade do perfil de estratégia, ao lado da
concentração de `equations.decision_score`. Ela corta o conjunto de pedidos
(`equations.admitted_set`) e, no leilão, também para o gasto
(`equations.concave_bids`) — uma regra, lida por cada mecanismo na moeda
dele.

POR QUE MÚLTIPLO DA MÉDIA, E NÃO VALOR ABSOLUTO
------------------------------------------------

Uma reserva absoluta sobre a participação **não sobrevive ao catálogo
crescer**: dobrar o número de disciplinas corta a participação média pela
metade, e o mesmo limiar passa a cortar o dobro. Como múltiplo da média, o
corte se lê em **múltiplos da indiferença** e é o mesmo em qualquer grade.

Ele também se adapta ao aluno. Um calouro e um veterano têm conjuntos
elegíveis de tamanhos bem diferentes, e com limiar absoluto o de conjunto
maior seria cortado mais fundo sem ter escolhido nada.

POR QUE SOBRE O SCORE, E NÃO SOBRE A UTILIDADE
-----------------------------------------------

Porque a mochila côncava ordena por **score**, e é contra a chave dela que a
parada tem de comparar. Com concentração ≠ 1 as duas escalas divergem — em
`c = 0,6` e `ũ ≈ 0,05`, o score é `0,05^0,6 ≈ 0,17`, mais de três vezes a
utilidade —, e um limiar calibrado sobre utilidades cortaria no lugar errado
em todo perfil menos o do meio.

Tomando a média sobre o próprio dicionário que a mochila recebe, o limiar
acompanha o expoente sozinho, inclusive o negativo do perfil Invertido.

Com seletividade 0 não há corte, e a função devolve 0 sem olhar os scores.

Não está no anteprojeto.
"""
from __future__ import annotations

from collections.abc import Mapping


def reserve_threshold(*, scores: Mapping[str, float], selectivity: float) -> float:
    if selectivity <= 0.0 or not scores:
        return 0.0
    return selectivity * sum(scores.values()) / len(scores)
