"""Tudo o que entra na conta do aluno ao fim de um período — anteprojeto, eq. (35)."""
from __future__ import annotations

from collections.abc import Iterable


def period_return(*, returns: Iterable[int]) -> int:
    return sum(returns)
