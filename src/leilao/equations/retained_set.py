"""O que o aluno leva, das vagas que obteve, quando a disponibilidade aperta.

    K_a^(t) = argmax { Σ_{x ∈ K} u_{a,x} : K ⊆ G_a^(t), Σ_{x ∈ K} w_x ≤ Ŵ_a^(t) }

`G_a^(t)` é o que ele obteve no período e `Ŵ_a^(t)` a carga efetiva
(`equations.effective_load`). O complemento, `G_a \\ K_a`, é o que ele
**exclui**.

É a mesma mochila 0-1 da eq. (50) — valor = utilidade, peso = carga —, só que
sobre o que foi conquistado em vez de sobre o que é elegível. A tabela é a
mesma, e mora em `equations._knapsack`: é lá que estão o desempate pela ordem
da grade, o corte pelo MDC dos pesos e a razão de ela não degenerar numa
ordenação.

Aqui sobra só o que é **deste** lado: os itens são o que o aluno obteve, o teto
é a carga efetiva, e obtida fora da linha de utilidades entra no fim, com
utilidade nula — o que não deveria existir, já que tudo o que se ganha era
elegível, mas não quebra a tabela se existir.

Não está no anteprojeto.
"""
from __future__ import annotations

from collections.abc import Iterable

from ._knapsack import knapsack


def retained_set(
    *,
    utilities: dict[str, float],
    hours: dict[str, int],
    obtained: Iterable[str],
    load: int,
) -> list[str]:
    if load < 0:
        raise ValueError("a carga efetiva não pode ser negativa")

    wanted = set(obtained)
    ordered = [name for name in utilities if name in wanted]
    # Obtida fora da linha de utilidades não deveria existir — tudo o que se
    # ganha era elegível —, mas se existir entra no fim, com utilidade nula.
    ordered += [name for name in sorted(wanted) if name not in utilities]

    # A capacidade nunca precisa passar da soma dos pesos: acima disso cabe
    # tudo, e a resposta não muda. O corte importa porque a carga efetiva **não
    # tem teto** — a disponibilidade é uma log-normal em horas —, e sem ele a
    # tabela acompanharia o sorteio até estourar a memória.
    ceiling = min(load, sum(hours[name] for name in ordered if hours[name] > 0))
    return knapsack(
        items=ordered, values=utilities, weights=hours, capacity=ceiling
    )
