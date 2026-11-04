"""O quantil da normal dividida — a inversa de `split_normal_cdf`.

    x = m + e · Φ⁻¹(q / 2w),               q < w
    x = m + d · Φ⁻¹(½ + (q − w)/2(1 − w)), q ≥ w

com **w = e/(e+d)**, a massa à esquerda da moda. Cada ramo reescala o quantil
para dentro da meia-normal correspondente e o devolve à escala original.

É por aqui que o desempenho base do aluno entra na nota: o sorteio guarda a
**posição** dele (o quantil), e a dificuldade e a tentativa mudam a
distribuição sob essa posição. O aluno no percentil 73 continua no percentil
73 quando a disciplina fica mais difícil — o que muda é a nota que o percentil
73 vale. É isso que mantém o desempenho como traço e não como sorte renovada a
cada tentativa.

Não está no anteprojeto.
"""
from __future__ import annotations

from statistics import NormalDist

_STANDARD = NormalDist()

# O quantil exatamente em 0 ou 1 devolveria infinito. O corte é bem mais fino
# do que o décimo em que a nota é arredondada, então não desloca nota nenhuma.
QUANTILE_GUARD = 1e-15


def split_normal_quantile(
    *, quantile: float, mode: float, left_sd: float, right_sd: float
) -> float:
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("o quantil deve estar em [0, 1]")
    if left_sd <= 0.0 or right_sd <= 0.0:
        raise ValueError("os dois desvios da normal dividida devem ser > 0")
    left_mass = left_sd / (left_sd + right_sd)
    if quantile < left_mass:
        inner = quantile / (2.0 * left_mass)
        sd = left_sd
    else:
        inner = 0.5 + (quantile - left_mass) / (2.0 * (1.0 - left_mass))
        sd = right_sd
    inner = min(1.0 - QUANTILE_GUARD, max(QUANTILE_GUARD, inner))
    return mode + sd * _STANDARD.inv_cdf(inner)
