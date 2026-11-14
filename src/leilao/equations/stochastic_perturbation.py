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

**O teto perdeu a função.** Ele existia para o objetivo somado da PLI, que
hoje não lê o ε (ver `wdp_solver`): quem o lê é a varredura gulosa e a
ditadura serial, e as duas só **comparam**. Medido: subir o teto de 3,3·10⁻⁸
para 1 devolve a mesma ordem, logo a mesma alocação. O que ainda faz trabalho
é a distinção — dois ε iguais seriam um empate de volta.
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


def per_agent(perturbations: dict[tuple[str, str], float]) -> dict[str, float]:
    """Um ε por **agente**, para quem prioriza o agente e não o par.

    A ditadura serial ordena alunos, não pares: o CR do aluno vale em tudo
    que ele pediu, e o desempate também tem de ser dele. Sai desta mesma
    matriz, pela chave lexicograficamente menor de cada agente — **nenhum
    sorteio novo**, que deslocaria o gerador e mudaria toda a simulação.

    Os valores continuam distintos entre agentes porque os da matriz são
    distintos entre si.
    """
    smallest: dict[str, str] = {}
    for agent_id, good_id in perturbations:
        if agent_id not in smallest or good_id < smallest[agent_id]:
            smallest[agent_id] = good_id
    return {
        agent_id: perturbations[(agent_id, good_id)]
        for agent_id, good_id in smallest.items()
    }
