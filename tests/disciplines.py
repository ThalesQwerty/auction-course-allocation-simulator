"""Monta disciplinas a partir da autoria por predecessores — a forma legível
nos testes — invertendo para `unlocks`, que é o que o motor guarda."""

from __future__ import annotations

from leilao.config import Discipline


def disciplines_from_predecessors(
    *entries: tuple[str, int, int] | tuple[str, int, int, tuple[str, ...]],
) -> list[Discipline]:
    """Cada entrada é `(nome, vagas, horas)` ou `(nome, vagas, horas, preds)`.

    `preds` são as disciplinas que desbloqueiam esta — a aresta antiga de
    pré-requisito. A saída usa `unlocks`.
    """
    parsed: list[tuple[str, int, int, tuple[str, ...]]] = []
    for entry in entries:
        if len(entry) == 3:
            name, seats, hours = entry  # type: ignore[misc]
            preds: tuple[str, ...] = ()
        else:
            name, seats, hours, preds = entry  # type: ignore[misc]
        parsed.append((name, seats, hours, preds))

    unlocks: dict[str, list[str]] = {name: [] for name, _, _, _ in parsed}
    for name, _, _, preds in parsed:
        for predecessor in preds:
            unlocks[predecessor].append(name)

    return [
        Discipline(name, seats=seats, hours=hours, unlocks=tuple(unlocks[name]))
        for name, seats, hours, _ in parsed
    ]
