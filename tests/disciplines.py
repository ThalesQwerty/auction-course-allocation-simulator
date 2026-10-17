"""Monta disciplinas a partir da autoria por predecessores.

A omissão de `entry` marca como entrada toda raiz — é o que os cenários de
matrícula garantida descrevem. Uma raiz que não é de entrada passa `False`.
"""

from __future__ import annotations

from leilao.config import Discipline


def disciplines_from_predecessors(
    *entries: tuple,
) -> list[Discipline]:
    """Cada entrada é `(nome, vagas, horas)`, `(nome, vagas, horas, entry)`,
    `(nome, vagas, horas, preds)` ou `(nome, vagas, horas, preds, entry)`.

    `preds` são as disciplinas que desbloqueiam esta. A saída usa `unlocks`.
    """
    parsed: list[tuple[str, int, int, tuple[str, ...], bool | None]] = []
    for entry in entries:
        explicit: bool | None = None
        if len(entry) == 3:
            name, seats, hours = entry
            preds: tuple[str, ...] = ()
        elif len(entry) == 4 and isinstance(entry[3], bool):
            name, seats, hours, explicit = entry
            preds = ()
        elif len(entry) == 4:
            name, seats, hours, preds = entry
        elif len(entry) == 5:
            name, seats, hours, preds, explicit = entry
        else:
            raise ValueError(f"entrada de disciplina inválida: {entry!r}")
        parsed.append((name, seats, hours, tuple(preds), explicit))

    unlocks: dict[str, list[str]] = {name: [] for name, _, _, _, _ in parsed}
    for name, _, _, preds, _ in parsed:
        for predecessor in preds:
            unlocks[predecessor].append(name)

    return [
        Discipline(
            name,
            seats=seats,
            hours=hours,
            unlocks=tuple(unlocks[name]),
            entry=is_entry if is_entry is not None else not preds,
        )
        for name, seats, hours, preds, is_entry in parsed
    ]
