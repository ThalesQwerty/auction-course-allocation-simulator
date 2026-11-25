"""Entidades do problema central P = (A, B, D, p, q, w, W, X) (anteprojeto, Seção 3)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Agent:
    """Um agente a in A. Em ambos os mecanismos, atua como uma mochila 0-1."""

    id: str
    capacity: float

    def __post_init__(self) -> None:
        if self.capacity < 0:
            raise ValueError(f"Agent {self.id!r}: capacity (W_a) must be >= 0")


@dataclass(frozen=True)
class Good:
    """Um bem escasso e discreto x in B."""

    id: str
    quantity: int
    weight: float

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError(f"Good {self.id!r}: quantity (q_x) must be >= 0")
        if self.weight <= 0:
            raise ValueError(f"Good {self.id!r}: weight (w_x) must be > 0")


@dataclass(frozen=True)
class Demand:
    """Um par de demanda (a, x) in D, com nível de preferência p_{a,x} > 0 (eq. 6)."""

    agent_id: str
    good_id: str
    preference: float
    tiebreak: float = 0.0

    def __post_init__(self) -> None:
        if self.preference < 0:
            raise ValueError(
                f"Demand ({self.agent_id!r}, {self.good_id!r}): preference (p_a,x) "
                "must be >= 0"
            )
        if self.tiebreak < 0:
            raise ValueError(
                f"Demand ({self.agent_id!r}, {self.good_id!r}): tiebreak must be >= 0"
            )


@dataclass(frozen=True)
class MutualExclusion:
    """Um clique Y in X de bens mutuamente excludentes (eq. 5) — ex.: choque de horário.
    """

    goods: frozenset[str]

    def __post_init__(self) -> None:
        if len(self.goods) < 2:
            raise ValueError("MutualExclusion clique must contain at least 2 goods")


@dataclass
class Problem:
    """A tupla P = (A, B, D, p, q, w, W, X) — eq. (9)."""

    agents: list[Agent]
    goods: list[Good]
    demands: list[Demand]
    exclusions: list[MutualExclusion] = field(default_factory=list)

    def __post_init__(self) -> None:
        agent_ids = {a.id for a in self.agents}
        good_ids = {g.id for g in self.goods}
        if len(agent_ids) != len(self.agents):
            raise ValueError("duplicate Agent ids in Problem.agents")
        if len(good_ids) != len(self.goods):
            raise ValueError("duplicate Good ids in Problem.goods")
        seen: set[tuple[str, str]] = set()
        for d in self.demands:
            if d.agent_id not in agent_ids:
                raise ValueError(f"Demand references unknown agent_id {d.agent_id!r}")
            if d.good_id not in good_ids:
                raise ValueError(f"Demand references unknown good_id {d.good_id!r}")
            key = (d.agent_id, d.good_id)
            if key in seen:
                raise ValueError(f"duplicate Demand for pair {key}")
            seen.add(key)
        for excl in self.exclusions:
            unknown = excl.goods - good_ids
            if unknown:
                raise ValueError(f"MutualExclusion references unknown goods {unknown}")

    def agent_ids(self) -> list[str]:
        return [a.id for a in self.agents]

    def good_ids(self) -> list[str]:
        return [g.id for g in self.goods]

    def demands_for_agent(self, agent_id: str) -> list[Demand]:
        return [d for d in self.demands if d.agent_id == agent_id]

    def demands_for_good(self, good_id: str) -> list[Demand]:
        return [d for d in self.demands if d.good_id == good_id]


Allocation = dict[tuple[str, str], int]
