"""Tudo o que entra na conta do aluno ao fim de um período — anteprojeto, eq. (35).

    Γ_a^(t) = Γ_min + Σ_{x ∈ cursadas} γ_{a,x}^(t)

Duas fontes, e só duas: o **crédito base** do período, igual para todos e
independente de desempenho, e a soma dos retornos da eq. (34), que dependem do
que o aluno pagou e de como foi. Não há outra entrada de crédito no modelo —
é o que torna o saldo da eq. (36) uma conta fechada e conferível.
"""
from __future__ import annotations

from collections.abc import Iterable


def period_return(*, base_credits: int, returns: Iterable[int]) -> int:
    return base_credits + sum(returns)
