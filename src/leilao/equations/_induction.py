"""Indução sobre a DAG de pré-requisitos, iterativa.

Duas grandezas da grade são a mesma recorrência sobre arestas opostas — a
altura anda pelos sucessores, o período pelos predecessores —, então a
travessia mora aqui e cada uma declara só o que a sua recorrência faz.

É iterativa, e não recursiva, porque uma cadeia longa estouraria a pilha do
Python antes de a grade ficar grande o bastante para incomodar. A pilha
explícita guarda pares `(nó, já expandido)`: na primeira visita o nó empilha
a si mesmo marcado e depois os vizinhos; na segunda, todos os vizinhos já têm
valor e a recorrência se aplica.

Ciclo é erro: a disciplina presa num ciclo não teria valor nenhum e nunca
ficaria elegível.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence


def induct(
    edges: dict[str, Sequence[str]],
    *,
    combine: Callable[[list[int]], int],
    on_cycle: Callable[[str], Exception],
) -> dict[str, int]:
    value: dict[str, int] = {}
    on_path: set[str] = set()
    for start in edges:
        if start in value:
            continue
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            name, expanded = stack.pop()
            if expanded:
                on_path.discard(name)
                value[name] = combine([value[n] for n in edges[name]])
                continue
            if name in value:
                continue
            if name in on_path:
                raise on_cycle(name)
            on_path.add(name)
            stack.append((name, True))
            stack.extend((n, False) for n in edges[name])
    return value
