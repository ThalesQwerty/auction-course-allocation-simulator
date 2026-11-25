"""O horário de cada turma — a distribuição circular."""
from __future__ import annotations

from collections.abc import Sequence

LABEL = "Horário"


def class_schedules(*, count: int, slots: int) -> tuple[str, ...]:
    """Os horários das `count` turmas, na ordem da grade."""
    total = max(slots, 1)
    return tuple(f"{LABEL} {index % total + 1}" for index in range(max(count, 0)))


def schedule_names(*, slots: int) -> tuple[str, ...]:
    """Todos os horários do cenário, na ordem da régua. É `G`."""
    return tuple(f"{LABEL} {index + 1}" for index in range(max(slots, 0)))


def schedule_cliques(
    schedule_of: dict[str, str], order: Sequence[str] = ()
) -> tuple[frozenset[str], ...]:
    """Os grupos de `G` com mais de uma turma — os únicos que restringem algo."""
    members: dict[str, set[str]] = {}
    for name, schedule in schedule_of.items():
        members.setdefault(schedule, set()).add(name)
    keys = [key for key in order if key in members] or list(members)
    return tuple(frozenset(members[key]) for key in keys if len(members[key]) > 1)
