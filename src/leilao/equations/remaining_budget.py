"""Saldo de créditos do agente ao fim da rodada — anteprojeto, eq. (27).

    C_a^(t,r+1) = C_a^(t,r) − Δ_a^(t,r),    Δ_a^(t,r) = Σ_{x ∈ B} δ_{a,x}

Só o consumo da eq. (25) desconta. O crédito comprometido num lance que
perdeu volta inteiro ao saldo e pode ser reapostado na rodada seguinte.
"""
from __future__ import annotations


def remaining_budget(
    *, budgets: dict[str, int], consumption: dict[tuple[str, str], int]
) -> dict[str, int]:
    remaining = dict(budgets)
    for (agent_id, _good_id), consumed in consumption.items():
        if agent_id in remaining:
            remaining[agent_id] -= consumed
    return remaining
