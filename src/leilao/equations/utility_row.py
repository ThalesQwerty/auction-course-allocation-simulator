"""A parte determinística da linha de utilidades — substitui a eq. (41).

    u_x = u'_x / Σ_y u'_y                           normalização da linha

O sorteio em si — uma log-normal de média logarítmica A_x e desvio σ — fica
em `behavior.draw_utilities`, porque depende do gerador. O que esta função
faz é o que vem depois dele, e é determinístico.

**O deslocamento por altura saiu.** A eq. (41) impunha `s_x > s_y ⇒ u_x > u_y`:
a disciplina que destrava uma cadeia mais longa valia sempre mais que a
terminal, qualquer que tivesse sido o sorteio. Isso punha valor curricular
dentro do que deveria ser gosto, e a correlação resultante entre utilidade e
posição na grade tornava indistinguíveis dois genes que deveriam ser eixos
separados.

No lugar dela, `equations.eligible_utility` redistribui a utilidade do que o
aluno não pode cursar sobre o que ele pode. A porteira continua valendo mais
— mas porque **acumulou o valor de tudo que destrava**, e não porque uma
desigualdade imposta disse que vale. Quem não quer nada à frente não é
empurrado para lá.

**A normalização** faz a grade inteira valer 1, o que dá ao número a leitura
de "fração do que o aluno quer" e ao ψ da eq. (51) um denominador fixo. Agora
ela deixou de ser dispensável: como a redistribuição conserva a massa, a
linha elegível também soma 1, e é isso que põe `alpha_u` na **mesma unidade**
da utilidade — o aluno compara participações, e a reserva é um valor nessa
mesma escala.

Opera sobre o eixo final de um array `(alunos, períodos, disciplinas)`.
"""
from __future__ import annotations

import numpy as np


def normalize_rows(raw: np.ndarray) -> np.ndarray:
    return raw / raw.sum(axis=2, keepdims=True)
