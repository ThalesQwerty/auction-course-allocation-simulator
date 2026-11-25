"""A média simples, com a convenção de conjunto vazio do projeto."""
from __future__ import annotations

from collections.abc import Sequence


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
