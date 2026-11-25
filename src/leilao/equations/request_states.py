"""Em que estado terminou cada disciplina que ainda falta ao aluno."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestStates:
    """Os seis estados de um recorte."""

    not_eligible: float
    not_requested: float
    refused: float
    excluded: float
    failed: float
    approved: float

    @property
    def total(self) -> float:
        """O denominador: quanto da grade ainda falta ao aluno."""
        return (
            self.not_eligible
            + self.not_requested
            + self.refused
            + self.excluded
            + self.failed
            + self.approved
        )

    @classmethod
    def average(cls, rows: "list[RequestStates]") -> "RequestStates":
        """A média por aluno de um recorte — nunca a soma."""
        if not rows:
            return cls(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        size = len(rows)
        return cls(
            not_eligible=sum(r.not_eligible for r in rows) / size,
            not_requested=sum(r.not_requested for r in rows) / size,
            refused=sum(r.refused for r in rows) / size,
            excluded=sum(r.excluded for r in rows) / size,
            failed=sum(r.failed for r in rows) / size,
            approved=sum(r.approved for r in rows) / size,
        )


def request_states(
    *,
    catalogue: Iterable[str],
    approved: Set[str],
    eligible: Iterable[str],
    requested: Set[str],
    won: Set[str],
    retained: Set[str],
    groups: Mapping[str, str] | None = None,
) -> RequestStates:
    """Classifica o período de **um** aluno."""

    def fold(names: Iterable[str]) -> set[str]:
        return {groups.get(name, name) if groups else name for name in names}

    retained = fold(retained)
    won = fold(won)
    requested = fold(requested)
    approved_now = retained & approved
    eligible_set = fold(eligible)
    previously = approved - approved_now
    return RequestStates(
        not_eligible=len(set(catalogue) - previously - eligible_set),
        not_requested=len(eligible_set - requested),
        refused=len(requested - won),
        excluded=len(won - retained),
        failed=len(retained - approved),
        approved=len(approved_now),
    )
