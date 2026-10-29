"""Carga horária que sobra ao agente depois de uma alocação — anteprojeto, eq. (14).

    W_a^(t,r+1) = W_a^(t,r) − Σ_{x ∈ B} w_x · z_{a,x}

A contraparte da eq. (13) do lado do aluno: cada vaga obtida desconta a carga
da disciplina do teto do período. É a restrição da eq. (4) sendo consumida ao
longo das rodadas.
"""
from __future__ import annotations


def remaining_capacity(
    *,
    capacity: dict[str, float],
    allocation: dict[tuple[str, str], int],
    weights: dict[str, float],
) -> dict[str, float]:
    remaining = dict(capacity)
    for (agent_id, good_id), taken in allocation.items():
        if taken and agent_id in remaining:
            remaining[agent_id] -= weights[good_id] * taken
    return remaining
