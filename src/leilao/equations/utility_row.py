"""A parte determinística da linha de utilidades — anteprojeto, eq. (41).

    u'_x = u_x + (max u − min u + 1) · s_x          invariante de altura
    u_x  = u'_x / Σ_y u'_y                          normalização da linha

O sorteio em si — uma log-normal de média logarítmica 0 e desvio σ — fica em
`behavior.draw_utilities`, porque depende do gerador. O que esta função faz é
o que vem depois dele, e é determinístico.

**O deslocamento por altura** impõe `s_x > s_y ⇒ u_x > u_y`: a disciplina que
destrava uma cadeia mais longa vale sempre mais que a terminal, qualquer que
tenha sido o sorteio. O passo é a amplitude da linha mais 1, o que garante a
desigualdade estrita até no empate `max = min`. Dentro de uma mesma altura a
ordem continua sendo a do sorteio — σ manda *dentro* da camada, a grade manda
*entre* camadas.

**A normalização** faz a grade inteira valer 1, o que dá ao número a leitura
de "fração do que o aluno quer" e ao ψ da eq. (51) um denominador fixo. Ela
preserva as desigualdades estritas entre positivos, e portanto a invariante
de altura. Não é necessária ao mecanismo: as duas mochilas comparam só razões
entre utilidades, de modo que a simulação sai idêntica sem ela.

Opera sobre o eixo final de um array `(alunos, períodos, disciplinas)`.
"""
from __future__ import annotations

import numpy as np

# O passo entre camadas é a amplitude da linha mais esta folga. Em 1 ela
# garante desigualdade estrita quando a linha é constante (max − min = 0).
HEIGHT_MARGIN = 1.0


def normalize_with_height_shift(raw: np.ndarray, heights: np.ndarray) -> np.ndarray:
    span = raw.max(axis=2, keepdims=True) - raw.min(axis=2, keepdims=True)
    shifted = raw + (span + HEIGHT_MARGIN) * heights.reshape(1, 1, -1)
    return shifted / shifted.sum(axis=2, keepdims=True)
