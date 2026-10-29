"""Preço de mercado de cada bem, a segundo preço — anteprojeto, eq. (24).

    π_x = max{ c_{a,x} : z_{a,x} = 0 }     (1 se ninguém perdeu)

O preço é o **maior lance mal-sucedido**: quem vence paga o que teria sido
preciso para deslocá-lo, e não o que ofereceu. Sem lance perdedor não houve
disputa, e o piso de 1 crédito é o valor da equação nesse caso — inclusive
quando o bem não recebeu lance nenhum.

Sempre inteiro: os lances (eq. 18) e o piso já o são.
"""
from __future__ import annotations

FLOOR = 1


def market_prices(
    *,
    good_ids: list[str],
    bids: dict[tuple[str, str], int],
    allocation: dict[tuple[str, str], int],
) -> dict[str, int]:
    highest_loser: dict[str, int] = {}
    for (agent_id, good_id), credits in bids.items():
        if allocation.get((agent_id, good_id), 0) == 0:
            highest_loser[good_id] = max(highest_loser.get(good_id, 0), credits)
    return {good_id: highest_loser.get(good_id, FLOOR) for good_id in good_ids}
