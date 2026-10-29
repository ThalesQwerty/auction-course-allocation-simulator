"""Semestralização: o quanto o aluno andou na grade desde que ingressou.

    σ_a = H̃_a / (W_a · idade_a)

Carga horária aprovada dividida pelo máximo que ela poderia ter sido. Vale 1
para quem encheu W_a e foi aprovado em tudo desde o ingresso, e mede o atraso
na progressão — que é justamente o que a matrícula por créditos deveria
reduzir.

`periods_completed` é a idade do aluno em períodos **no instante do recorte**:
durante as rodadas de t ele completou t − t_a períodos, e ao fim de t
completou t − t_a + 1 — que é exatamente o intervalo coberto pela carga
aprovada do mesmo recorte. Quem acabou de ingressar tem idade 0 e entra como
0, não como 0/0.

Como W_a é do cenário e igual para todos, σ compara todo mundo contra o mesmo
teto. Não consta no anteprojeto.
"""
from __future__ import annotations


def semestralization(
    *, approved_hours: int, max_hours: int, periods_completed: int
) -> float:
    if periods_completed <= 0 or max_hours <= 0:
        return 0.0
    return approved_hours / (max_hours * periods_completed)
