"""Créditos efetivamente consumidos por uma demanda vencedora — anteprojeto, eq. (25).

    δ_{a,x} = min(c_{a,x}, π_x)      se z_{a,x} = 1
            = 0                      caso contrário

Quem vence paga o preço de mercado (eq. 24), não o que apostou — e paga o
lance quando este é menor que o preço, o que só acontece quando o bem teve
vaga sobrando. **Lance perdedor não consome nada**, e é essa gratuidade que
faz o aluno apostar tudo em toda rodada.
"""
from __future__ import annotations


def consumption(
    *,
    bids: dict[tuple[str, str], int],
    allocation: dict[tuple[str, str], int],
    prices: dict[str, int],
) -> dict[tuple[str, str], int]:
    return {
        (agent_id, good_id): min(credits, prices[good_id])
        for (agent_id, good_id), credits in bids.items()
        if allocation.get((agent_id, good_id), 0)
    }
