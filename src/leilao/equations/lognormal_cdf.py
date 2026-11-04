"""A acumulada da log-normal.

    F(x) = Φ((ln x − μ) / σ),   x > 0
    F(x) = 0,                   x ≤ 0

O suporte é (0, ∞): a disponibilidade nunca é negativa, e isso vem da família,
não de uma truncagem imposta.

Serve para ler de volta o que o perfil declarou — `1 − F(W_a)` tem de devolver
a chance de alcançar a carga máxima — e para as grandezas derivadas que a tela
mostra ao pé da curva: a mediana, e quanto da massa fica abaixo de uma carga
qualquer.

Não está no anteprojeto.
"""
from __future__ import annotations

import math

from .split_normal_cdf import standard_normal_cdf


def lognormal_cdf(*, value: float, log_mean: float, log_sd: float) -> float:
    if log_sd <= 0.0:
        raise ValueError("o desvio logarítmico deve ser > 0")
    if value <= 0.0:
        return 0.0
    return standard_normal_cdf((math.log(value) - log_mean) / log_sd)
