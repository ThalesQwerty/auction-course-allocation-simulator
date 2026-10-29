"""P̂(aprovar): a taxa de aprovação que a disciplina anuncia.

    P̂(aprovar x) = aprovações_x / matriculados_x

O outro sinal publicado, ao lado de `win_estimate`. É a dificuldade da
disciplina **já filtrada pela população** — não a dificuldade declarada, que
o aluno não vê.

**Sem matrícula vale 1**: ninguém cursou, logo não houve reprovação
observável, e o termo de progresso cai no neutro.

Um efeito colateral que é bom: o sinal é **enviesado de forma diferente em
cada mecanismo**. Na ordenação por CR a disciplina escassa é cursada por quem
tem CR alto, então ela parece mais fácil do que é. Isso é característica do
modelo, não defeito — é o que um aluno real também leria.
"""
from __future__ import annotations


def pass_rate_estimate(*, approvals: int, enrolled: int) -> float:
    if enrolled <= 0:
        return 1.0
    return approvals / enrolled
