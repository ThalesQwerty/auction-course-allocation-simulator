"""A matriz de perturbações que garante solução ótima única (Seção 7.1.2).

    ε_{a,x} ∈ ( 0, 1/(|A|²·|B|) ),  todos distintos

O teto é o que mantém a perturbação **irrelevante para a alocação**: mesmo
somando todos os ε de uma solução inteira, o total fica abaixo de 1/|A| de um
crédito, de modo que ela nunca desloca uma solução de preferência agregada
maior. Ela só decide onde lance, viés e ordem de desempate empatam — e é
isso que torna única a solução ótima que o PLI encontra (Seção 6.3).

Os valores saem de uma grade fina dentro do intervalo, amostrados **sem
reposição**: é o que garante que sejam estritamente distintos, o que um
sorteio contínuo garantiria só com probabilidade 1. A grade tem quatro vezes
mais pontos que chaves para que a amostra não se aproxime de esgotá-la.

`seed` é o que torna a matriz reprodutível, como exige a Seção 7.3.
"""
from __future__ import annotations

import numpy as np

# Pontos da grade por chave. Folga suficiente para a amostra sem reposição
# não degenerar numa permutação da grade inteira.
GRID_DENSITY = 4


def stochastic_perturbations(
    keys: list[tuple[str, str]], *, num_agents: int, num_goods: int, seed: int
) -> dict[tuple[str, str], float]:
    if not keys:
        return {}
    upper_bound = 1.0 / (num_agents**2 * max(num_goods, 1))
    rng = np.random.default_rng(seed)
    grid = np.linspace(
        upper_bound / (len(keys) + 1),
        upper_bound,
        num=len(keys) * GRID_DENSITY,
        endpoint=False,
    )
    chosen = rng.choice(grid, size=len(keys), replace=False)
    rng.shuffle(chosen)
    return {key: float(value) for key, value in zip(keys, chosen)}
