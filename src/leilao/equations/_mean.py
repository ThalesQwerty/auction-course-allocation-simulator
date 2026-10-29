"""A média simples, com a convenção de conjunto vazio do projeto.

Várias métricas de recorte são a média de uma grandeza por aluno, e todas
tratam o conjunto vazio do mesmo jeito: **zero**. Não é o valor certo em
abstrato — a média de nada não existe —, mas aqui quem publica a métrica já
decidiu que há alguém a medir; o recorte sem ninguém sai com `metrics = None`
antes de chegar aqui, e o zero nunca aparece num gráfico.

Privado de propósito: cada métrica que o usa tem arquivo próprio, com nome e
docstring próprios, para que a revisão seja equação a equação.
"""
from __future__ import annotations

from collections.abc import Sequence


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
