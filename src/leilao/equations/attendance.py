"""Aproveitamento: quanto da carga obtida o aluno de fato cursou."""
from __future__ import annotations

from collections.abc import Iterable, Mapping


def attendance(
    *, won: Iterable[str], attended: Iterable[str], hours: Mapping[str, int]
) -> float | None:
    """`None` quando o aluno não obteve vaga nenhuma no período."""
    obtained = sum(hours[name] for name in won)
    if obtained <= 0:
        return None
    return sum(hours[name] for name in attended) / obtained
