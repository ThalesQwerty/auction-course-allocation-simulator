"""Coeficiente de rendimento do aluno — anteprojeto, eq. (49).

    N_a = Σ_{x ∈ H_a} w_x · n_{a,x} / Σ_{x ∈ H_a} w_x

Média das notas ponderada pela carga horária das disciplinas **cursadas**
(H_a), aprovadas ou não — reprovação pesa no CR, que é o que faz dele um
critério de mérito e não de progresso.

A nota que entra é a **maior já obtida** em cada disciplina, não a da última
tentativa: é a mesma que decide a aprovação, e sem isso uma recursada infeliz
rebaixaria um histórico já consolidado.

Sem disciplina cursada a média é 0/0, e adota-se 0,0 — o aluno ainda não tem
histórico, que é a situação de todo calouro.
"""
from __future__ import annotations

from collections.abc import Set


def grade_average(
    *, taken: Set[str], grades: dict[str, float], hours: dict[str, int]
) -> float:
    if not taken:
        return 0.0
    total_hours = sum(hours[name] for name in taken)
    weighted = sum(hours[name] * grades.get(name, 0.0) for name in taken)
    return weighted / total_hours
