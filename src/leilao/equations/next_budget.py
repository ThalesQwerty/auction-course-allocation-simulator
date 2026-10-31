"""O orçamento do período seguinte — anteprojeto, eqs. (36) e (37).

    C_a^(t+1,1) = C_a^(t,1) − gasto_a^(t) + Γ_a^(t)        memória "carry"
    C_a^(t+1,1) = Γ_min                                    memória "none"
    C_a^(1,1)   = Γ_min                                    eq. (37)

A eq. (36) é a do anteprojeto: o que sobrou atravessa o período. Note que
**não é poupança** — o aluno aposta o orçamento inteiro e paga o segundo
preço, então o que sobra é o que ele não foi cobrado, não o que guardou.

A variante `none` substitui a equação por um orçamento que recomeça em Γ_min
todo período: o passado do aluno não entra no poder de compra dele por via
alguma.

Note que com ela **o retorno fica inerte** — `period_return` entra e não é
usado —, de modo que a simulação é idêntica com e sem `f_γ` (medido:
relatórios iguais, período a período). O retorno só existe onde há acúmulo, e
é por isso que memória e retorno **não formam um cruzamento 2x2**: o segundo é
aninhado no primeiro. As duas fontes de memória têm sinais opostos de
incentivo — a sobra premia quem pagou barato, o retorno premia quem aprovou —,
e separá-las exige o degrau do meio, não uma quarta combinação.
"""
from __future__ import annotations

from typing import Literal

Memory = Literal["none", "carry"]


def next_budget(
    memory: Memory, *, started_with: int, spent: int, period_return: int, base_credits: int
) -> int:
    if memory == "none":
        return base_credits
    if memory == "carry":
        return started_with - spent + period_return
    raise ValueError(f"memória de crédito desconhecida: {memory!r}")
