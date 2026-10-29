"""Fator de desempate entre agentes — anteprojeto, eq. (20).

    α̂_{a,x} = (|A| − α_{a,x}) / |A|

`rank` é a posição do agente na ordem de desempate do bem x (1 = prioritário,
|A| = último). O resultado fica em [0, 1): sempre menos que um crédito, de modo
que o desempate nunca inverte uma diferença de lance, e maior quanto mais
prioritário o agente.
"""
from __future__ import annotations


def tie_break_factor(rank: int, num_agents: int) -> float:
    if num_agents <= 0:
        raise ValueError("num_agents must be > 0")
    if not 1 <= rank <= num_agents:
        raise ValueError(f"rank must be in [1, {num_agents}], got {rank}")
    return (num_agents - rank) / num_agents
