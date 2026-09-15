"""Desempate, viés administrativo e perturbação estocástica (Seção 7.1.2).

Estas três matrizes (alpha, beta, epsilon) não se alteram entre rodadas de
alocação e servem para garantir que toda demanda (a, x) receba uma
preferência positiva e única, mesmo quando os lances/prioridades brutos
empatam — condição necessária para que o resolvedor de PLI produza uma
solução ótima única (Seção 6.3).
"""
from __future__ import annotations

import numpy as np


def tie_break_factor(rank: int, num_agents: int) -> float:
    """alpha_hat_{a,x} = (|A| - alpha_{a,x}) / |A|  — eq. (20).

    `rank` é a posição do agente na ordem de desempate para o bem x
    (1 = primeiro/prioritário, |A| = último). O resultado está em [0, 1),
    estritamente menor que 1 crédito, e é maior quanto mais prioritário o
    agente for na ordem de desempate.
    """
    if num_agents <= 0:
        raise ValueError("num_agents must be > 0")
    if not (1 <= rank <= num_agents):
        raise ValueError(f"rank must be in [1, {num_agents}], got {rank}")
    return (num_agents - rank) / num_agents


def rectify_bias(bias: dict[tuple[str, str], int]) -> dict[tuple[str, str], int]:
    """beta_hat_{a,x} = beta_{a,x} - beta_min  — eq. (21). Torna o viés >= 0.

    Um viés positivo aumenta artificialmente a prioridade do lance do agente
    em relação aos demais; negativo a reduz; zero não a influencia.
    """
    if not bias:
        return {}
    beta_min = min(bias.values())
    return {key: value - beta_min for key, value in bias.items()}


def stochastic_perturbations(
    keys: list[tuple[str, str]],
    *,
    num_agents: int,
    num_goods: int,
    seed: int,
) -> dict[tuple[str, str], float]:
    """Matriz epsilon de perturbações estocásticas — Seção 7.1.2.

    Cada elemento epsilon_{a,x} in (0, 1/(|A|^2 * |B|)), sem repetição, usada
    apenas para desempatar preferências e garantir unicidade da solução ótima
    (eq. discutida na Seção 6.3). `seed` garante reprodutibilidade: a mesma
    entrada sempre gera os mesmos resultados (requisito metodológico do
    anteprojeto, Seção 7.3).
    """
    if not keys:
        return {}
    upper_bound = 1.0 / (num_agents**2 * max(num_goods, 1))
    rng = np.random.default_rng(seed)
    # Valores estritamente distintos: amostra sem reposição em uma grade fina
    # dentro de (0, upper_bound) e embaralha.
    grid = np.linspace(upper_bound / (len(keys) + 1), upper_bound, num=len(keys) * 4, endpoint=False)
    chosen = rng.choice(grid, size=len(keys), replace=False)
    rng.shuffle(chosen)
    return {key: float(value) for key, value in zip(keys, chosen)}
