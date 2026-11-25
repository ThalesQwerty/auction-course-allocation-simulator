"""O que a repetição faz com a chance de aprovar."""
from __future__ import annotations


def attempt_approval(
    *, approval_rate: float, repetition_gain: float, previous_attempts: int
) -> float:
    """A chance de aprovar na tentativa seguinte a `previous_attempts` cursadas."""
    if not 0.0 < approval_rate < 1.0:
        raise ValueError("a probabilidade de aprovação deve estar em (0, 1)")
    if repetition_gain < 0.0:
        raise ValueError("o ganho por repetição deve ser >= 0")
    if previous_attempts < 0:
        raise ValueError("as tentativas anteriores não podem ser negativas")
    return approval_rate ** (1.0 / (1.0 + repetition_gain * previous_attempts))
