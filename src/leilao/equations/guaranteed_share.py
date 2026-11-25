"""Quanto o sistema cobra do ingressante por cada vaga garantida."""
from __future__ import annotations


def guaranteed_share(*, budget: int, entry_count: int) -> int:
    return budget // entry_count
