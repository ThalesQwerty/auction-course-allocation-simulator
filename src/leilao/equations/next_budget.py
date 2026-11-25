"""O orçamento do período seguinte — anteprojeto, eqs. (36) e (37).

    C_a^(t+1,1) = clamp( C_a^(t,1) − gasto_a^(t) + Γ_a^(t), C_min, C_max )
    C_a^(1,1)   = C_min                       eq. (37)

O miolo é o da eq. (36) do anteprojeto: o que sobrou atravessa o período. Note
que **não é poupança** — o aluno aposta o orçamento inteiro e paga o segundo
preço, então o que sobra é o que ele não foi cobrado, não o que guardou.

Houve uma variante `"none"` aqui até 24/11/2026 — o orçamento recomeçando em
`C_min` todo período, sem acúmulo nenhum. Ela existia para separar o que a
**moeda** compra do que o **acúmulo** compra, e saiu com o fechamento do
escopo: o trabalho compara a ordenação por CR contra o leilão com acúmulo e
retorno, e mais nada. Com ela saiu também o único jeito de tornar o retorno
inerte, porque o retorno só existe onde há acúmulo.

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
parte que passaria da faixa.

`max_credits=None` desliga o teto; o piso não se desliga.
"""
from __future__ import annotations


def next_budget(
    *,
    started_with: int,
    spent: int,
    period_return: int,
    min_credits: int,
    max_credits: int | None = None,
) -> int:
    carried = started_with - spent + period_return
    if max_credits is not None:
        carried = min(carried, max_credits)
    return max(carried, min_credits)
