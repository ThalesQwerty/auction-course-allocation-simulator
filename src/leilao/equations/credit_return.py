"""Retorno de créditos por disciplina cursada — anteprojeto, eq. (34).

    γ_{a,x}^(t) = f_γ(preço pago, nota obtida)

O anteprojeto deixa `f_γ` em aberto: ela é o eixo de experimentação da
Seção 7.3.2. São quatro políticas, da mais restritiva à mais generosa:

    none    0                            nada volta — o crédito gasto sai do
                                         sistema, e a única entrada é o Γ_min
    unit    1 se aprovado                premia aprovar, não o quanto se pagou
    full    preço se aprovado            o crédito só se perde na reprovação
    ratio   round(nota/10 · preço)       premia desempenho acima da nota de
                                         corte, e devolve algo a quem reprova

`ratio` é a única que separa dois alunos aprovados pela nota, e portanto a
única com chance de recriar o incentivo que a ordenação por CR dá de graça —
é por isso que ela entra como braço próprio da comparação.

Em `ratio` o `round` do Python desempata para o par (`round(2.5) == 2`), e o
empate exato é frequente aqui: as notas andam de 0,1 em 0,1 e os preços são
inteiros pequenos. O viés é o mesmo para todo aluno, que é o que importa na
comparação entre políticas.
"""
from __future__ import annotations

from typing import Literal

Policy = Literal["none", "unit", "full", "ratio"]


def credit_return(policy: Policy, *, paid: int, grade: float, min_grade: float) -> int:
    if policy == "none":
        return 0
    if policy == "unit":
        return 1 if grade >= min_grade else 0
    if policy == "full":
        return paid if grade >= min_grade else 0
    if policy == "ratio":
        return round(grade / 10 * paid)
    raise ValueError(f"política de retorno de créditos desconhecida: {policy!r}")
