"""O orçamento do período seguinte — anteprojeto, eqs. (36) e (37).

    C_a^(t+1,1) = C_a^(t,1) − gasto_a^(t) + Γ_a^(t)        memória "carry"
    C_a^(t+1,1) = Γ_min                                    memória "none"
    C_a^(1,1)   = Γ_min                                    eq. (37)

A eq. (36) é a do anteprojeto: o que sobrou atravessa o período. Note que
**não é poupança** — o aluno aposta o orçamento inteiro e paga o segundo
preço, então o que sobra é o que ele não foi cobrado, não o que guardou.

A variante `none` substitui a equação por um orçamento que recomeça em Γ_min
todo período. É o degrau de baixo da escada de acúmulo e o único braço em que
o passado do aluno não entra no poder de compra dele por via alguma — sem ele
não dá para separar o efeito da sobra do efeito do retorno, que têm sinais
opostos de incentivo: a sobra premia quem pagou barato, o retorno premia quem
aprovou.
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
