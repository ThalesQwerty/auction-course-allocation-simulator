"""O conjunto em que o aluno ainda pode obter vaga nesta rodada — anteprojeto, eq. (15).

    B_a^(t,r) = { x : q_x^(t,r) > 0 ∧ w_x ≤ W_a^(t,r) ∧ z_{a,x} = 0 }

Três filtros sobre o conjunto elegível (eq. 42): a disciplina tem vaga livre,
a carga dela ainda cabe no que resta do teto do aluno, e ele não a conquistou
neste período. Disciplina fora daqui não recebe lance nem solicitação — é o
caso que o histórico individual mostra como "sem lance".

O conjunto é **o mesmo nos dois mecanismos**; o que muda é o que o aluno faz
com ele: repartir créditos (eq. 44) ou escolher quais pedir (eq. 50).

A ordem da saída é a de `eligible`, que é a ordem da grade no cenário — é dela
que as duas mochilas tiram o desempate entre disciplinas.
"""
from __future__ import annotations

from collections.abc import Iterable, Set


def available_goods(
    *,
    eligible: Iterable[str],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: float,
    already_won: Set[str],
) -> list[str]:
    return [
        name
        for name in eligible
        if seats[name] > 0 and hours[name] <= capacity and name not in already_won
    ]
