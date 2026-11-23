"""Fecho transitivo da DAG de pré-requisitos, e a inversão dele.

    seq(X) = { Y | X ∈ req(Y) }      os sucessores, transitivamente
    req(Y) = { X | Y ∈ seq(X) }      os pré-requisitos, transitivamente

As duas funções da monografia são **uma a inversa exata da outra**, e é essa
propriedade — e só ela — que faz `Σ_{X ∈ M_a} U_{a,X} = 1` em
`equations.utility`: cada sucessor é reivindicado por exatamente os
ancestrais elegíveis que o contam, e as frações se recompõem inteiras. Por
isso `inverse_edges` **inverte o fecho já calculado** em vez de rodar um
segundo fecho sobre as arestas opostas. Os dois caminhos dão o mesmo conjunto
numa DAG, mas só o primeiro garante a inversão por construção, sem depender
de a travessia ter concordado consigo mesma.

É iterativa, e não recursiva, pelo mesmo motivo de `_induction`: uma cadeia
longa estouraria a pilha do Python antes de a grade ficar grande o bastante
para incomodar.

O memo recebe o conjunto vazio **antes** de descer, o que corta ciclo sem
travar — a validação do cenário já os rejeita, e quem levanta é a altura.

A ordem de saída é a de declaração da grade, e é determinística: ela entra na
soma do numerador da utilidade, onde a ordem muda o último dígito.
"""
from __future__ import annotations


def transitive_closure(edges: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Tudo que se alcança de cada nó, sem incluir o próprio nó."""
    rank = {name: position for position, name in enumerate(edges)}
    reached: dict[str, set[str]] = {}
    for start in edges:
        if start in reached:
            continue
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            name, expanded = stack.pop()
            if expanded:
                whole: set[str] = set()
                for neighbor in edges.get(name, ()):
                    whole.add(neighbor)
                    whole |= reached.get(neighbor, frozenset())
                reached[name] = whole
                continue
            if name in reached:
                continue
            reached[name] = set()
            stack.append((name, True))
            stack.extend((n, False) for n in edges.get(name, ()))
    return {
        name: tuple(sorted(reached[name], key=lambda n: rank.get(n, len(rank))))
        for name in edges
    }


def inverse_edges(edges: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """A aresta oposta, nó a nó. Preserva a ordem de declaração dos dois
    lados: a dos nós, nas chaves; a dos vizinhos, na iteração da entrada."""
    opposite: dict[str, list[str]] = {name: [] for name in edges}
    for name, neighbors in edges.items():
        for neighbor in neighbors:
            opposite.setdefault(neighbor, []).append(name)
    return {name: tuple(opposite[name]) for name in edges}
