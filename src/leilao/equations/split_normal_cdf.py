"""A acumulada da normal dividida.

    F(x) = 2e/(e+d) · Φ((x − m)/e),                  x < m
    F(x) = e/(e+d) + 2d/(e+d) · (Φ((x − m)/d) − ½),  x ≥ m

onde **m** é a moda, **e** o desvio do lado esquerdo e **d** o do direito. A
densidade é a normal de desvio `e` à esquerda da moda e a de desvio `d` à
direita, reescaladas pelo fator comum `√(2/π)/(e+d)` para fechar em 1.

As duas peças encostam na moda com o mesmo valor e com derivada zero dos dois
lados: o pico é liso. O que quebra é a **segunda** derivada — a curvatura salta
de −A/e² para −A/d² —, e é essa quebra que permite o desvio assimétrico.

A massa à esquerda da moda é `e/(e+d)`, o que dá a leitura direta dos dois
desvios: eles repartem a probabilidade na mesma proporção em que alongam a
cauda. Com `e = d` a distribuição é a normal comum.

Não está no anteprojeto: a distribuição de nota é posterior a ele.
"""
from __future__ import annotations

import math


def standard_normal_cdf(value: float) -> float:
    """Φ — a acumulada da normal padrão, por `erfc` para não perder a cauda."""
    return 0.5 * math.erfc(-value / math.sqrt(2.0))


def split_normal_cdf(
    *, value: float, mode: float, left_sd: float, right_sd: float
) -> float:
    if left_sd <= 0.0 or right_sd <= 0.0:
        raise ValueError("os dois desvios da normal dividida devem ser > 0")
    left_mass = left_sd / (left_sd + right_sd)
    if value < mode:
        return 2.0 * left_mass * standard_normal_cdf((value - mode) / left_sd)
    right_mass = right_sd / (left_sd + right_sd)
    return left_mass + 2.0 * right_mass * (
        standard_normal_cdf((value - mode) / right_sd) - 0.5
    )
