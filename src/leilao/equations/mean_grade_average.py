"""CR médio de um recorte — anteprojeto, eq. (56).

    N̄ = (1/|A|) · Σ_{a ∈ A} N_a

O CR usado é o **vigente no início do período**: as notas do período só entram
no CR do período seguinte, como numa matrícula real. O calouro entra com
N_a = 0 e por isso fica fora do recorte medido, senão N̄ cairia todo período de
ingresso sem que nada tivesse acontecido com os alunos.
"""
from __future__ import annotations

from collections.abc import Sequence

from ._mean import mean


def mean_grade_average(grade_averages: Sequence[float]) -> float:
    return mean(grade_averages)
