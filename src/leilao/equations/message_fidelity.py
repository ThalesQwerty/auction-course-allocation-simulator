"""Fidelidade da mensagem: quanto da preferência sobrevive à tradução."""
from __future__ import annotations

import math


def message_fidelity(
    *, utilities: dict[str, float], message: dict[str, float]
) -> float:
    names = [name for name, utility in utilities.items() if utility > 0.0]
    if not names:
        return 0.0
    wanted = [utilities[name] for name in names]
    sent = [message.get(name, 0.0) for name in names]
    norm_wanted = math.sqrt(sum(value * value for value in wanted))
    norm_sent = math.sqrt(sum(value * value for value in sent))
    if norm_wanted <= 0.0 or norm_sent <= 0.0:
        return 0.0
    return sum(a * b for a, b in zip(wanted, sent)) / (norm_wanted * norm_sent)
