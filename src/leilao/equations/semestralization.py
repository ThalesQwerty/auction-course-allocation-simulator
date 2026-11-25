"""Semestralização: o quanto o aluno andou na grade desde que ingressou."""
from __future__ import annotations


def semestralization(
    *, approved_hours: int, max_hours: int, periods_completed: int
) -> float:
    if periods_completed <= 0 or max_hours <= 0:
        return 0.0
    return approved_hours / (max_hours * periods_completed)
