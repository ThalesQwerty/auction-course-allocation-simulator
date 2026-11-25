"""A turma de entrada de um calouro."""
from __future__ import annotations

from collections.abc import Sequence


def entry_block(*, ordinal: int, cohort: int, classes: int) -> int:
    """O bloco da coorte a que o ordinal pertence."""
    if classes <= 0:
        raise ValueError("uma disciplina de entrada precisa de pelo menos uma turma")
    if cohort <= 0:
        return 0
    return min(max(ordinal * classes // cohort, 0), classes - 1)


def rotated_index(*, block: int, offset: int, classes: int) -> int:
    """O índice da turma que o bloco recebe, girado `offset` posições."""
    if classes <= 0:
        raise ValueError("uma disciplina de entrada precisa de pelo menos uma turma")
    return (block + offset) % classes


def entry_class(
    *, ordinal: int, cohort: int, classes: Sequence[str], offset: int = 0
) -> str:
    if not classes:
        raise ValueError("uma disciplina de entrada precisa de pelo menos uma turma")
    block = entry_block(ordinal=ordinal, cohort=cohort, classes=len(classes))
    return classes[rotated_index(block=block, offset=offset, classes=len(classes))]


def entry_class_load(
    *, cohort: int, classes: Sequence[str], offset: int = 0
) -> dict[str, int]:
    """Quantos calouros cada turma recebe — a contagem dos blocos, já girada."""
    load = {name: 0 for name in classes}
    for ordinal in range(max(cohort, 0)):
        load[
            entry_class(
                ordinal=ordinal, cohort=cohort, classes=classes, offset=offset
            )
        ] += 1
    return load
