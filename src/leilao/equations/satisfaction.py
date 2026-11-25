"""Satisfação do aluno num período — anteprojeto, eq. (51)."""
from __future__ import annotations

from collections.abc import Iterable, Mapping


def satisfaction(
    *, utilities: Mapping[str, float], allocated: Iterable[str]
) -> float:
    return sum(utilities.get(name, 0.0) for name in allocated)
