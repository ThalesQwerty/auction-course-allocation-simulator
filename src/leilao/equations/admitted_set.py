"""O corte da seletividade — quais disciplinas entram no pedido."""
from __future__ import annotations


def admitted_set(
    *, scores: dict[str, float], reserve: float = 0.0
) -> dict[str, float]:
    if reserve <= 0.0:
        return scores
    return {name: score for name, score in scores.items() if score >= reserve}
