"""O que o aluno leva, das vagas que obteve, quando a disponibilidade aperta.

    K_a^(t) = argmax { Σ_{x ∈ K} u_{a,x} : K ⊆ G_a^(t), Σ_{x ∈ K} w_x ≤ Ŵ_a^(t) }

`G_a^(t)` é o que ele obteve no período e `Ŵ_a^(t)` a carga efetiva
(`equations.effective_load`). O complemento, `G_a \\ K_a`, é o que ele
**exclui**.

É a mesma mochila 0-1 da eq. (50) — valor = utilidade, peso = carga —, só que
sobre o que foi conquistado em vez de sobre o que é elegível.

**Não degenera numa ordenação.** A heurística natural seria tirar da menor
utilidade para a maior até caber, e ela erra assim que as cargas diferem. Com
teto de 122 h e as obtidas Algoritmos (90 h, u 0,22), Cálculo (60 h, 0,13) e
Física (60 h, 0,11): a ordenação tira Física, não cabe, tira Cálculo e retém
0,22; a mochila retém Cálculo + Física, 120 h, utilidade 0,24. A heurística
sacrifica duas disciplinas baratas para salvar uma cara.

ORDEM DE DESEMPATE
------------------

Mesma regra do resto do motor: entre subconjuntos de utilidade igual, ganha o
que contém a disciplina **listada primeiro** no cenário. A ordem dos itens sai
de `utilities`, que é a ordem da grade, e o desempate compara as posições
escolhidas lexicograficamente — menor vence, isto é, índice mais baixo vence.

Com utilidade sorteada o empate tem probabilidade zero. A regra existe para
que um cenário escrito à mão não dependa da ordem de iteração, que é a mesma
exigência de determinismo da Seção 7.3.

Disciplina de carga nula não consome o teto, então é sempre retida e nem entra
na tabela.

Não está no anteprojeto.
"""
from __future__ import annotations

from collections.abc import Iterable


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

    free = [name for name in ordered if hours[name] <= 0]
    items = [(name, utilities.get(name, 0.0), hours[name]) for name in ordered if hours[name] > 0]

    # A capacidade da mochila nunca precisa passar da soma dos pesos: acima
    # disso cabe tudo, e a resposta não muda. O corte importa porque a carga
    # efetiva **não tem teto** — a disponibilidade é uma log-normal em horas —,
    # e sem ele a tabela do DP acompanharia o sorteio até estourar a memória.
    ceiling = min(load, sum(weight for _, _, weight in items))

    # dp[capacidade] = (utilidade acumulada, posições escolhidas). A tupla de
    # posições é o critério de desempate, e nunca a chave de ordenação.
    dp: list[tuple[float, tuple[int, ...]]] = [(0.0, ()) for _ in range(ceiling + 1)]
    for index, (_, utility, weight) in enumerate(items):
        if weight > ceiling:
            continue
        for capacity in range(ceiling, weight - 1, -1):
            value, chosen = dp[capacity - weight]
            candidate = (value + utility, chosen + (index,))
            current = dp[capacity]
            if candidate[0] > current[0] or (
                candidate[0] == current[0] and candidate[1] < current[1]
            ):
                dp[capacity] = candidate

    kept = {items[index][0] for index in dp[ceiling][1]}
    kept.update(free)
    return [name for name in ordered if name in kept]
