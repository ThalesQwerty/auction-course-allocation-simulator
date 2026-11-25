"""Indução sobre a DAG de pré-requisitos, iterativa."""
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
