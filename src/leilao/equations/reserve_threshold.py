"""A utilidade de reserva: a opção externa do aluno contra o que ele pode cursar.

    s_a^(t) = S_a^(t) / ( S_a^(t) + Σ_{X ∈ M_a^(t)} I_{a,X}^(t) )

`S_a^(t)` é a **seletividade** do período — o valor da opção externa, quanto
vale para o aluno não cursar disciplina nenhuma —, e é o único eixo de
estratégia dele. `s_a^(t)` é a participação dessa opção no interesse total
das elegíveis (`equations.eligible_interest`), e é o limiar contra o qual ele
compara cada disciplina:

- **pede X** se `U_{a,X} ≥ s_a^(t)` (`equations.admitted_set`);
- **investe o k-ésimo crédito em X** se `U_{a,X}/k ≥ s_a^(t)`
  (`equations.concave_bids`).

Uma regra, dois usos, um por mecanismo: no CR não há investimento marginal
que se possa interromper, então lá o corte do conjunto é tudo o que existe.

A SELETIVIDADE É UMA ALTERNATIVA A MAIS NO BOLO
------------------------------------------------

A forma `S / (S + ΣI)` é a da **opção externa**: a seletividade entra no
mesmo bolo das elegíveis e fica com a fatia dela. É o que "utilidade de
reserva" quer dizer em desenho de mecanismos — o payoff de não participar,
contra o qual se escreve a restrição de participação —, e não o preço de
reserva do vendedor.

A ESCALA DE `S` É A DO INTERESSE
---------------------------------

`S` é um valor na escala de `I`, e não um múltiplo de disciplina: é assim que
a monografia o define, e é o que faz a razão cair em [0, 1). Como
`equations.interest_row` normaliza a linha sobre a **grade inteira**, `ΣI`
das elegíveis é a fração da grade que o aluno pode cursar agora, e `S` se lê
na mesma moeda: **quanto da grade inteira vale não estudar**. Daí a ordem de
grandeza da mediana ser de centésimos, e não de unidades.

A consequência prática: o limiar medido em utilidades médias é `S / Ī`, com
`Ī = ΣI/|M_a|` o interesse médio de uma elegível. Crescer o **conjunto
elegível** não mexe nele — `ΣI` e `|M_a|` crescem juntos, a utilidade média
cai na mesma proporção que a reserva, e a *fração* pedida fica onde estava.
Crescer a **grade** mexe: a normalização da linha faz `Ī` encolher, e o mesmo
`S` passa a cortar mais. Trocar de grade pede recalibrar a mediana.

**O denominador é o das elegíveis, não o da utilidade.** `equations.utility`
normaliza por `Σ_{M_a ∪ seq(M_a)} I`, que é maior porque absorve o lookahead
dos sucessores nos *numeradores* — as duas normalizações põem a mesma massa
total (1) sobre o conjunto elegível, e o lookahead só a redistribui lá dentro.
Descontá-lo outra vez aqui faria a reserva encolher só porque o aluno tem
grade longa pela frente, e ele pediria mais por isso.

**Com `S = 0` a reserva é zero** e o aluno pede tudo que é elegível: é o
especulador, e é o perfil que a Seção 2.2 do anteprojeto diz que o CR
incentiva. Com a seletividade sorteada de uma log-normal ele não aparece
exatamente, mas a cauda baixa dela se comporta como ele.

Não está no anteprojeto.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Behavior:
    """O perfil de estratégia: como o aluno traduz utilidade em mensagem.

    **É função, não matriz.** A utilidade é resorteada a cada período, então
    um perfil com um valor por par (aluno, disciplina) descreveria o que
    fazer com a linha deste semestre e não diria nada sobre a do próximo.

    O valor é **do período**: a seletividade sai de uma log-normal com nível
    basilar, como o interesse, então ela muda de semestre para semestre em
    torno da exigência permanente do aluno. Quem o atribui antes das rodadas é
    `simulation.period`.
    """

    # S_a^(t) — a seletividade, na **escala do interesse**. 0 desliga o corte:
    # o aluno pede tudo que é elegível e gasta o orçamento inteiro.
    selectivity: float = 0.0


NEUTRAL = Behavior()


def reserve_threshold(*, selectivity: float, interest: float) -> float:
    """`interest` é `Σ_{X ∈ M_a^(t)} I_{a,X}` — o interesse total das
    **disciplinas** elegíveis, de `equations.eligible_interest`.

    Sem elegíveis não há o que cortar, e o limiar sai 0 em vez de 1.
    """
    if selectivity <= 0.0 or interest <= 0.0:
        return 0.0
    return selectivity / (selectivity + interest)
