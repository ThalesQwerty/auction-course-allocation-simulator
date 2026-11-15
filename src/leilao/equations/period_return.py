"""Tudo o que entra na conta do aluno ao fim de um período — anteprojeto, eq. (35).

    Γ_a^(t) = Σ_{x ∈ cursadas} γ_{a,x}^(t)

**Uma fonte, e só uma**: a soma dos retornos da eq. (34), que dependem do que o
aluno pagou e de como foi. O anteprojeto somava aqui também um crédito base
Γ_min, igual para todos e independente de desempenho; ele saiu. O que se
chamava Γ_min virou `C_min`, o **piso do orçamento** da eq. (36) — não uma
entrada que se soma todo período, mas o valor abaixo do qual o saldo não cai.

A consequência é que o retorno passa a ser a **única** porta de entrada de
crédito novo no sistema, e é o que torna o saldo da eq. (36) uma conta fechada
e conferível: todo crédito acima do piso foi ganho em disciplina cursada.
"""
from __future__ import annotations

from collections.abc import Iterable


def period_return(*, returns: Iterable[int]) -> int:
    return sum(returns)
