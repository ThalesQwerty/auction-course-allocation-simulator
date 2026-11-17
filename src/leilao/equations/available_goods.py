"""O conjunto em que o aluno ainda pode obter vaga nesta rodada — anteprojeto, eq. (15).

    B_a^(t,r) = { x : q_x^(t,r) > 0 ∧ w_x ≤ W_a^(t,r) ∧ z_{a,x} = 0 }

Três filtros sobre o conjunto elegível (eq. 42): a turma tem vaga livre, a
carga dela ainda cabe no que resta do teto do aluno, e ele não conquistou
**nada que conflite com ela** neste período.

O terceiro filtro é por **grupo de exclusão**, não por bem, e é ele que
estende os cliques da eq. (5) para além da rodada: o WDP impõe `Σ z ≤ 1`
dentro de uma rodada, mas nada impediria ganhar a turma A na rodada 1 e a
turma C na rodada 2 da mesma disciplina — ou duas turmas no mesmo horário.

Os grupos são `E = M ∪ G`: a disciplina da turma e o horário dela. Sem
`conflicts` cada bem é o próprio grupo, e o filtro volta a ser o de antes de
as turmas existirem. Turma fora daqui não recebe lance nem solicitação — é o
caso que o histórico individual mostra como "sem lance".

O conjunto é **o mesmo nos dois mecanismos**; o que muda é o que o aluno faz
com ele: repartir créditos (eq. 44) ou escolher quais pedir (eq. 50).

A ordem da saída é a de `eligible`, que é a ordem da grade no cenário — é dela
que as duas mochilas tiram o desempate entre disciplinas.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence, Set


def available_goods(
    *,
    eligible: Iterable[str],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: float,
    already_won: Set[str],
    conflicts: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    taken: set[str] = set()
    for name in already_won:
        taken.update(conflicts[name] if conflicts else (name,))
    return [
        name
        for name in eligible
        if seats[name] > 0
        and hours[name] <= capacity
        and taken.isdisjoint(conflicts[name] if conflicts else (name,))
    ]
