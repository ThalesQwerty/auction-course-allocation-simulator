"""Quanto do que o aluno quer está ao alcance dele — anteprojeto, eq. (43).

    U_a^(t) = Σ_{x ∈ elegível} u_{a,x}^(t)

Como a linha inteira soma 1 (`utility_row`) e o recorte elegível **não é
renormalizado**, U_a fica abaixo de 1 sempre que algo estiver fora do alcance
do aluno, e vale 1 só na situação-limite em que a grade inteira lhe é
elegível.

É **leitura, não alavanca**: nenhuma decisão depende dela. As duas mochilas
comparam só razões entre utilidades, de modo que multiplicar a linha por uma
constante não muda lance, pedido nem ψ. O que U_a responde é "quanto do que
este aluno quer ele pode sequer disputar agora" — e é o fator que converte o
ψ de denominador fixo da eq. (51) na leitura antiga, sobre o elegível:
`ψ_elegível = ψ / U_a`.
"""
from __future__ import annotations


def reachable_utility(eligible_utilities: dict[str, float]) -> float:
    return sum(eligible_utilities.values())
