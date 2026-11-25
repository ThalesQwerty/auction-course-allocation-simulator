"""Alcance: quantas disciplinas cada uma destrava, transitivamente."""
from __future__ import annotations

from .curriculum_closure import transitive_closure


def curriculum_reach(unlocks: dict[str, tuple[str, ...]]) -> dict[str, int]:
    return {
        name: len(reached) for name, reached in transitive_closure(unlocks).items()
    }
