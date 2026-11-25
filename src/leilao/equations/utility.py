"""A utilidade: o interesse do aluno sobre o que ele pode cursar agora."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def utility(
    *,
    interest: Mapping[str, float],
    eligible: Sequence[str],
    reachable: Mapping[str, Sequence[str]],
    required: Mapping[str, Sequence[str]],
    classes: Mapping[str, Sequence[str]] | None = None,
    schedule_interest: Mapping[str, float] | None = None,
    schedule_of: Mapping[str, str] | None = None,
) -> dict[str, float]:
    """`interest` é por **disciplina** e `schedule_interest` por **horário**;"""
    chosen = list(eligible)
    if not chosen:
        return {}
    open_now = set(chosen)

    def names_of(discipline: str) -> Sequence[str]:
        return classes[discipline] if classes else (discipline,)

    numerator: dict[str, float] = {}
    denominator = sum(interest.get(discipline, 0.0) for discipline in chosen)
    counted: set[str] = set()
    for discipline in chosen:
        accumulated = interest.get(discipline, 0.0)
        for heir in reachable.get(discipline, ()):
            if heir in open_now:
                continue
            gates = sum(
                1 for previous in required.get(heir, ()) if previous in open_now
            )
            if not gates:
                continue
            accumulated += interest.get(heir, 0.0) / gates
            if heir not in counted:
                counted.add(heir)
                denominator += interest.get(heir, 0.0)
        numerator[discipline] = accumulated

    best_schedule = max(schedule_interest.values(), default=0.0) if schedule_interest else 0.0

    def schedule_factor(name: str) -> float:
        if not schedule_interest or not schedule_of or best_schedule <= 0.0:
            return 1.0
        slot = schedule_of.get(name)
        if slot is None:
            return 1.0
        return schedule_interest.get(slot, 0.0) / best_schedule

    result: dict[str, float] = {}
    for discipline in chosen:
        share = numerator[discipline] / denominator if denominator > 0.0 else 0.0
        for name in names_of(discipline):
            result[name] = share * schedule_factor(name)
    return result
