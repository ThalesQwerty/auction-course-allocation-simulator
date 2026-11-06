"""O conjunto em que o aluno ainda pode obter vaga nesta rodada — anteprojeto, eq. (15).

    B_a^(t,r) = { x : q_x^(t,r) > 0 ∧ w_x ≤ W_a^(t,r) ∧ z_{a,x} = 0 }

Três filtros sobre o conjunto elegível (eq. 42): a turma tem vaga livre, a
carga dela ainda cabe no que resta do teto do aluno, e ele não conquistou
**nenhuma turma do grupo dela** neste período.

O terceiro filtro é por **grupo**, não por bem, e é ele que estende o clique
da eq. (5) para além da rodada: o WDP impõe `Σ z ≤ 1` dentro de uma rodada,
mas nada impediria ganhar a turma A na rodada 1 e a turma C na rodada 2 da
mesma disciplina. Sem `groups` cada bem é o próprio grupo, e o filtro volta
a ser o de antes de as turmas existirem. Disciplina fora daqui não recebe lance nem solicitação — é o
caso que o histórico individual mostra como "sem lance".

O conjunto é **o mesmo nos dois mecanismos**; o que muda é o que o aluno faz
com ele: repartir créditos (eq. 44) ou escolher quais pedir (eq. 50).

A ordem da saída é a de `eligible`, que é a ordem da grade no cenário — é dela
que as duas mochilas tiram o desempate entre disciplinas.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Set


def available_goods(
    *,
    eligible: Iterable[str],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: float,
    already_won: Set[str],
    groups: Mapping[str, str] | None = None,
) -> list[str]:
    taken = {groups[name] if groups else name for name in already_won}
    return [
        name
        for name in eligible
        if seats[name] > 0
        and hours[name] <= capacity
        and (groups[name] if groups else name) not in taken
    ]
