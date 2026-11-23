"""O interesse total do que o aluno pode cursar — o denominador da reserva.

    ΣI_a^(t) = Σ_{X ∈ M_a^(t)} I_{a,X}^(t)

`I_{a,X}` é o interesse da **disciplina**: a média do interesse pelas turmas
dela, a mesma definição que `equations.utility` usa no numerador. Aqui ela só
é somada sobre o conjunto elegível, e o resultado é o que `reserve_threshold`
põe no bolo junto com a seletividade.

**É interesse, não utilidade.** A reserva é a única decisão do aluno que lê o
interesse cru — todo o resto (lance, pedido, ψ) lê a saída de
`equations.utility`. A razão é a definição: a opção externa vale uma fração
do que *existe* para o aluno cursar, e a utilidade já gastou a massa dela na
normalização (soma 1, qualquer que seja o conjunto elegível), de modo que
nela não sobra escala contra a qual comparar a opção externa.

**Não desconta o lookahead.** `equations.utility` divide por
`Σ_{M_a ∪ seq(M_a)} I`, que é maior porque absorve o interesse dos sucessores
nos *numeradores*. Aqui o denominador é só o das elegíveis: o que está
trancado não é alternativa a não estudar neste período.

Não está no anteprojeto.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def eligible_interest(
    *,
    interest: Mapping[str, float],
    eligible: Sequence[str],
    classes: Mapping[str, Sequence[str]] | None = None,
) -> float:
    """`interest` é por **turma**; `eligible` é por **disciplina**. `classes`
    mapeia cada disciplina nas turmas dela; omitido, cada disciplina é a
    própria turma."""
    total = 0.0
    for discipline in eligible:
        names = classes[discipline] if classes else (discipline,)
        if not names:
            continue
        total += sum(interest.get(name, 0.0) for name in names) / len(names)
    return total
