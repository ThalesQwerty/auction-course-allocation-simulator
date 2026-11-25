"""Fecho transitivo da DAG de pré-requisitos, e a inversão dele."""
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
    """A aresta oposta, nó a nó. Preserva a ordem de declaração dos dois"""
    opposite: dict[str, list[str]] = {name: [] for name in edges}
    for name, neighbors in edges.items():
        for neighbor in neighbors:
            opposite.setdefault(neighbor, []).append(name)
    return {name: tuple(opposite[name]) for name in edges}
