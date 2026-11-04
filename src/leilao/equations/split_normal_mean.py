"""A média da normal dividida.

    μ = m + √(2/π) · (d − e)

A moda é o parâmetro de locação, mas não é a média: cada meia-normal contribui
com `√(2/π)` vezes o próprio desvio, e o que sobra é a diferença entre os dois
lados. Com `e = d` o termo some e a média volta a ser a moda, como na normal
comum.

O sinal se lê sozinho: cauda esquerda mais longa (`e > d`) puxa a média para
**baixo** da moda. É o formato que distribuição de nota costuma ter — a maioria
perto do pico, e uma minoria que vai muito mal espalhada lá embaixo —, e por
isso a média de um perfil fica tipicamente 1 a 2 pontos abaixo da moda dele.

Não está no anteprojeto.
"""
from __future__ import annotations

import math

_HALF_NORMAL_MEAN = math.sqrt(2.0 / math.pi)


def split_normal_mean(*, mode: float, left_sd: float, right_sd: float) -> float:
    if left_sd <= 0.0 or right_sd <= 0.0:
        raise ValueError("os dois desvios da normal dividida devem ser > 0")
    return mode + _HALF_NORMAL_MEAN * (right_sd - left_sd)
