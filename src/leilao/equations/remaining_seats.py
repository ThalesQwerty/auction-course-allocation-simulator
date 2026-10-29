"""Vagas que sobram de um bem depois de uma alocação — anteprojeto, eq. (13).

    q_x^(t,r+1) = q_x^(t,r) − Σ_{a ∈ A} z_{a,x}

É o estoque andando de uma rodada para a seguinte. Bens sem demanda atendida
atravessam a rodada intactos.
"""
from __future__ import annotations


def remaining_seats(
    *, seats: dict[str, int], allocation: dict[tuple[str, str], int]
) -> dict[str, int]:
    remaining = dict(seats)
    for (_agent_id, good_id), taken in allocation.items():
        if taken and good_id in remaining:
            remaining[good_id] -= taken
    return remaining
