"""Equidade de Jain — anteprojeto, eq. (55).

    φ = (Σ v_a)² / (n · Σ v_a²)

Vale 1 quando todos recebem a mesma satisfação e 1/n quando um único agente
concentra tudo, de modo que o piso depende do tamanho do recorte — compare φ
entre braços do mesmo cenário, não entre cenários de populações diferentes.

A indeterminação 0/0 (ninguém alocado) é tomada como 0.
"""
from __future__ import annotations

from collections.abc import Sequence


def jain_index(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    square_sum = sum(value**2 for value in values)
    if square_sum == 0:
        return 0.0
    # O teto é exato na matemática — φ = 1 com todos iguais — mas a soma de
    # quadrados em ponto flutuante devolve 1 + 1e-16. Cortar aqui evita que
    # uma métrica declarada em [1/n, 1] saia da própria faixa.
    return min(1.0, sum(values) ** 2 / (len(values) * square_sum))
