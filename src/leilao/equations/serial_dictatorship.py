"""Ditadura serial: a distribuição da linha de base — Seção 7.3.1."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def serial_dictatorship(
    *,
    requests: list[tuple[str, str]],
    priority: dict[str, float],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: dict[str, int],
    conflicts: Mapping[str, Sequence[str]] | None = None,
    tiebreak: dict[str, float] | None = None,
) -> list[tuple[str, str]]:
    remaining = dict(seats)
    room = dict(capacity)
    wanted: dict[str, list[str]] = {}
    for student_id, name in requests:
        wanted.setdefault(student_id, []).append(name)

    granted: list[tuple[str, str]] = []
    rank = tiebreak or {}
    for student_id in sorted(wanted, key=lambda s: (-priority[s], -rank.get(s, 0.0), s)):
        served: set[str] = set()
        for name in wanted[student_id]:
            groups = conflicts[name] if conflicts else (name,)
            if not served.isdisjoint(groups):
                continue
            if remaining.get(name, 0) > 0 and room.get(student_id, 0) >= hours[name]:
                remaining[name] -= 1
                room[student_id] -= hours[name]
                served.update(groups)
                granted.append((student_id, name))
    return granted
