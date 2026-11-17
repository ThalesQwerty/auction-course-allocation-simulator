"""Preço de mercado de cada bem, a segundo preço — anteprojeto, eq. (24).

    π_x = max{ c_{a,x} : z_{a,x} = 0 }     (1 se ninguém perdeu)

O preço é o **maior lance mal-sucedido**: quem vence paga o que teria sido
preciso para deslocá-lo, e não o que ofereceu. Sem lance perdedor não houve
disputa, e o piso de 1 crédito é o valor da equação nesse caso — inclusive
quando o bem não recebeu lance nenhum.

QUEM CONTA COMO PERDEDOR, COM TURMAS E HORÁRIOS
------------------------------------------------

Só quem **não ganhou nada que conflite** com a turma. Quem apostou nas turmas
A, B e C de uma disciplina e foi roteado para C não foi recusado em A e B:
foi atendido. O mesmo vale para o horário — quem levou uma turma às terças de
manhã não foi recusado na outra que acontece no mesmo horário, porque não
poderia cursá-la de todo modo.

Contá-lo como perdedor ali faria cada membro do grupo inflar o preço das
turmas do próprio grupo, e o efeito apareceria como "turmas encarecem tudo" —
artefato, não resultado.

Os grupos são os de `E = M ∪ G`. Sem `conflicts` cada bem é o próprio grupo e
a regra volta a ser a de antes: perdeu quem não levou aquele bem.

Sempre inteiro: os lances (eq. 18) e o piso já o são.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

FLOOR = 1


def market_prices(
    *,
    good_ids: list[str],
    bids: dict[tuple[str, str], int],
    allocation: dict[tuple[str, str], int],
    conflicts: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, int]:
    served: set[tuple[str, str]] = set()
    for (agent_id, good_id), taken in allocation.items():
        if not taken:
            continue
        for group in conflicts[good_id] if conflicts else (good_id,):
            served.add((agent_id, group))
    highest_loser: dict[str, int] = {}
    for (agent_id, good_id), credits in bids.items():
        groups = conflicts[good_id] if conflicts else (good_id,)
        if any((agent_id, group) in served for group in groups):
            continue
        highest_loser[good_id] = max(highest_loser.get(good_id, 0), credits)
    return {good_id: highest_loser.get(good_id, FLOOR) for good_id in good_ids}
