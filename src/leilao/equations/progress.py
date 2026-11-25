"""Progresso do aluno na grade."""
from __future__ import annotations


def progress(
    *,
    approved_required_hours: int,
    approved_elective_hours: int,
    required_hours: int,
    elective_hours_needed: int,
) -> float:
    total = required_hours + elective_hours_needed
    if total <= 0:
        return 0.0
    counted = approved_required_hours + min(
        approved_elective_hours, elective_hours_needed
    )
    return counted / total
