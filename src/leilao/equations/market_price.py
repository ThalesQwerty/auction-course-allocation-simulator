"""Preço de mercado de cada bem, a segundo preço — anteprojeto, eq. (24).

    π_x = max{ c_{a,x} : z_{a,x} = 0 }     (1 se ninguém perdeu)

O preço é o **maior lance mal-sucedido**: quem vence paga o que teria sido
preciso para deslocá-lo, e não o que ofereceu. Sem lance perdedor não houve
disputa, e o piso de 1 crédito é o valor da equação nesse caso — inclusive
quando o bem não recebeu lance nenhum.

QUEM CONTA COMO PERDEDOR, COM TURMAS
-------------------------------------

Só quem **não ganhou nada no grupo** da turma. Quem apostou nas turmas A,
B e C de uma disciplina e foi roteado para C não foi recusado em A e B:
foi atendido. Contá-lo como perdedor ali faria cada membro do grupo
inflar o preço das turmas do próprio grupo, e o efeito apareceria como
"turmas encarecem tudo" — artefato, não resultado.

Sem `groups` cada bem é o próprio grupo e a regra volta a ser a de antes:
perdeu quem não levou aquele bem.

Sempre inteiro: os lances (eq. 18) e o piso já o são.
"""
from __future__ import annotations

from collections.abc import Mapping

FLOOR = 1


def market_prices(
    *,
    good_ids: list[str],
    bids: dict[tuple[str, str], int],
    allocation: dict[tuple[str, str], int],
    groups: Mapping[str, str] | None = None,
) -> dict[str, int]:
    served: set[tuple[str, str]] = {
        (agent_id, groups[good_id] if groups else good_id)
        for (agent_id, good_id), taken in allocation.items()
        if taken
    }
    highest_loser: dict[str, int] = {}
    for (agent_id, good_id), credits in bids.items():
        group = groups[good_id] if groups else good_id
        if (agent_id, group) in served:
            continue
        highest_loser[good_id] = max(highest_loser.get(good_id, 0), credits)
    return {good_id: highest_loser.get(good_id, FLOOR) for good_id in good_ids}
