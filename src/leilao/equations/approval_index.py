"""Índice de aprovação: a facilidade que a disciplina anuncia.

    aprovação_x = (aprovações_x + 1) / (alocações_x + 2)

O outro sinal publicado, ao lado de `supply_index`. Substitui
`pass_rate_estimate`, que era a razão crua. É a dificuldade da disciplina
**já filtrada pela população** — não a dificuldade declarada, que o aluno não
vê.

A SUAVIZAÇÃO DE LAPLACE
------------------------

O `+1/+2` é **suavização aditiva** — a regra de sucessão de Laplace —, isto
é, uma pseudocontagem em cada lado sobre uma prior Beta(1, 1). Na forma geral
seria `(x + α)/(N + α·d)` com `d = 2` categorias e `α = 1`, e a leitura
bayesiana é a média da posterior: antes de ver qualquer resultado, presume-se
meio a meio.

Ela corrige a variância absurda de contagem pequena — uma disciplina com uma
alocação e uma aprovação não vale 100%, vale 2/3 — e, de graça, resolve o
*cold start*: **disciplina nunca ofertada dá exatamente 1/2**, que é o
neutro. A prior uniforme *é* "sem informação", então não é preciso tratar o
caso à parte como em `supply_index`.

De quebra, garante `0 < aprovação < 1` estrito para qualquer contagem, o que
torna a potência de `decision_score` sempre segura: nem base zero com
expoente negativo, nem saturação em 1.

Um efeito colateral que é bom: o sinal é **enviesado de forma diferente em
cada mecanismo**. Na ordenação por CR a disciplina escassa é cursada por quem
tem CR alto, então ela parece mais fácil do que é. Isso é característica do
modelo, não defeito — é o que um aluno real também leria.

Não está no anteprojeto.
"""
from __future__ import annotations


def approval_index(*, approvals: int, allocations: int) -> float:
    if approvals < 0 or allocations < 0:
        raise ValueError("as contagens não podem ser negativas")
    if approvals > allocations:
        raise ValueError("não se pode aprovar mais do que se alocou")
    return (approvals + 1) / (allocations + 2)
