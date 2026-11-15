"""O orçamento do período seguinte — anteprojeto, eqs. (36) e (37).

    C_a^(t+1,1) = clamp( C_a^(t,1) − gasto_a^(t) + Γ_a^(t), C_min, C_max )
    C_a^(t+1,1) = C_min                       memória "none"
    C_a^(1,1)   = C_min                       eq. (37)

O miolo é o da eq. (36) do anteprojeto: o que sobrou atravessa o período. Note
que **não é poupança** — o aluno aposta o orçamento inteiro e paga o segundo
preço, então o que sobra é o que ele não foi cobrado, não o que guardou.

A variante `none` substitui a equação por um orçamento que recomeça em `C_min`
todo período: o passado do aluno não entra no poder de compra dele por via
alguma.

Note que com ela **o retorno fica inerte** — `period_return` entra e não é
usado —, de modo que a simulação é idêntica com e sem `f_γ` (medido:
relatórios iguais, período a período). O retorno só existe onde há acúmulo, e
é por isso que memória e retorno **não formam um cruzamento 2x2**: o segundo é
aninhado no primeiro.

A FAIXA DO ORÇAMENTO (C_min, C_max)
------------------------------------

Não está no anteprojeto, que tinha um Γ_min **somado** todo período e nenhum
teto. Aqui os dois parâmetros delimitam a mesma grandeza — o orçamento com que
o aluno abre o período —, e a conta do meio é livre para passar dos dois lados:

- **o piso (`C_min`)** garante que ninguém fique sem poder de compra. Ele não é
  um ganho: quem termina o período acima dele não recebe nada por existir, e é
  isso que faz do retorno da eq. (34) a única entrada de crédito novo. Quem
  gasta tudo e não aprova nada reabre em `C_min` — não em zero, e também não em
  `C_min` *mais* o que sobrou.
- **o teto (`C_max`)** corta o acúmulo. Sem ele a eq. (36) acumula sem limite, e
  medido no cenário cheio com um ganho base de 60 o saldo chegava a **900
  créditos** — quinze vezes a base — em quem é seletivo o bastante para não
  gastar. O aluno que atravessa períodos sem pedir nada compra um período
  inteiro depois, e isso é poder de compra vindo da abstenção, não do
  desempenho: o oposto do que o retorno existe para premiar.

Os dois cortam **depois** da conta do período, de modo que gasto e retorno
continuam sendo creditados por inteiro — o que se perde (ou se ganha) é só a
parte que passaria da faixa. Com `memory="none"` ambos são inertes, porque ali
o saldo é `C_min` por construção.

`max_credits=None` desliga o teto; o piso não se desliga.
"""
from __future__ import annotations

from typing import Literal

Memory = Literal["none", "carry"]


def next_budget(
    memory: Memory,
    *,
    started_with: int,
    spent: int,
    period_return: int,
    min_credits: int,
    max_credits: int | None = None,
) -> int:
    if memory == "none":
        return min_credits
    if memory == "carry":
        carried = started_with - spent + period_return
        if max_credits is not None:
            carried = min(carried, max_credits)
        return max(carried, min_credits)
    raise ValueError(f"memória de crédito desconhecida: {memory!r}")
