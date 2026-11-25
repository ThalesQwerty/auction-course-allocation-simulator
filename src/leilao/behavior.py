"""O sorteio do interesse e a utilidade que sai dele (Seção 7.2.4)."""
from __future__ import annotations

import sys
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING

import numpy as np

from .config import SimulationConfig
from .equations import (
    NEUTRAL,
    Behavior,
    admitted_set,
    concave_bids,
    eligible_interest,
    reflect_array,
    shock_scale,
    standard_normal_quantiles,
    reserve_threshold,
    utility,
)
from .equations.interest_histogram import BINS as DISTRIBUTION_BINS
from .equations.interest_histogram import interest_histogram

if TYPE_CHECKING:
    from .population import Student

UNDERFLOW_GUARD = sys.float_info.min

__all__ = [
    "DISTRIBUTION_BINS",
    "NEUTRAL",
    "UNDERFLOW_GUARD",
    "Behavior",
    "InterestMatrix",
    "compute_bids",
    "decide",
    "draw_interest",
    "draw_schedule_interest",
    "interest_distribution",
    "utility_matrix",
]


def _shock_by_discipline(config: SimulationConfig) -> np.ndarray:
    """A estabilidade de cada disciplina, com o valor do cenário como padrão."""
    return np.array(
        [
            shock_scale(
                config.interest_stability if d.stability is None else d.stability
            )
            for d in config.disciplines
        ],
        dtype=float,
    ).reshape(1, 1, -1)


class InterestMatrix(Mapping[tuple[str, int], dict[str, float]]):
    """O interesse sorteado, guardado como o array que o sorteio produz."""

    __slots__ = ("_values", "_columns", "_row_of_student")

    def __init__(
        self,
        values: np.ndarray,
        columns: tuple[str, ...],
        row_of_student: dict[str, int],
    ) -> None:
        self._values = values
        self._columns = columns
        self._row_of_student = row_of_student

    @property
    def periods(self) -> int:
        return int(self._values.shape[1])

    def __getitem__(self, key: tuple[str, int]) -> dict[str, float]:
        student_id, period = key
        row = self._row_of_student.get(student_id)
        if row is None or not 1 <= period <= self.periods:
            raise KeyError(key)
        return dict(zip(self._columns, self._values[row, period - 1].tolist()))

    def __iter__(self) -> Iterator[tuple[str, int]]:
        for student_id in self._row_of_student:
            for period in range(1, self.periods + 1):
                yield (student_id, period)

    def __len__(self) -> int:
        return len(self._row_of_student) * self.periods


def draw_interest(
    students: list["Student"], config: SimulationConfig, rng: np.random.Generator
) -> InterestMatrix:
    """I^(t) — o interesse por **disciplina**, uma linha por (aluno, período)."""
    groups = [d.name for d in config.disciplines]
    shape = (len(students), config.periods, len(groups))
    anchors = rng.random(size=(len(students), 1, len(groups)))
    shocks = rng.normal(0.0, 1.0, size=shape) * _shock_by_discipline(config)
    quantiles = reflect_array(anchors + shocks)
    log = config.interest_sigma * standard_normal_quantiles(quantiles)
    log = log + config.interest_mean
    values = np.maximum(np.exp(log), UNDERFLOW_GUARD)
    return InterestMatrix(
        values=values,
        columns=tuple(groups),
        row_of_student={student.id: a for a, student in enumerate(students)},
    )


def draw_schedule_interest(
    students: list["Student"], config: SimulationConfig, rng: np.random.Generator
) -> InterestMatrix:
    """h^(t) — o interesse por **horário**, uma linha por (aluno, período)."""
    slots = list(config.schedules())
    if not slots:
        return InterestMatrix(
            values=np.ones((len(students), config.periods, 0)),
            columns=(),
            row_of_student={s.id: a for a, s in enumerate(students)},
        )
    shape = (len(students), config.periods, len(slots))
    anchors = rng.random(size=(len(students), 1, len(slots)))
    shocks = rng.normal(0.0, 1.0, size=shape) * shock_scale(
        config.interest_stability
    )
    quantiles = reflect_array(anchors + shocks)
    log = config.schedule_sigma * standard_normal_quantiles(quantiles)
    return InterestMatrix(
        values=np.maximum(np.exp(log), UNDERFLOW_GUARD),
        columns=tuple(slots),
        row_of_student={student.id: a for a, student in enumerate(students)},
    )


def interest_distribution(
    rows: InterestMatrix, bins: int = DISTRIBUTION_BINS
) -> list[float]:
    """O histograma do interesse — ver `equations.interest_histogram`."""
    return interest_histogram(rows.values(), bins)


def utility_matrix(
    *,
    interest: dict[str, float],
    student: "Student",
    config: SimulationConfig,
    schedule_interest: dict[str, float] | None = None,
) -> dict[str, float]:
    """ũ_{a,·}^(t): a utilidade do aluno no período — o interesse dele, visto"""
    approved = student.approved(config.min_grade)
    return utility(
        interest=interest,
        eligible=config.eligible_disciplines(approved),
        reachable=config.reachable_by_discipline(),
        required=config.required_by_discipline(),
        classes=config.classes_by_discipline(),
        schedule_interest=schedule_interest,
        schedule_of=config.schedule_by_class() if schedule_interest else None,
    )


def interest_total(
    *, interest: dict[str, float], student: "Student", config: SimulationConfig
) -> float:
    """Σ_{X ∈ M_a^(t)} I_{a,X}: o denominador da reserva — ver"""
    approved = student.approved(config.min_grade)
    return eligible_interest(
        interest=interest,
        eligible=config.eligible_disciplines(approved),
    )


def decide(
    *,
    utilities: dict[str, float],
    behavior: Behavior = NEUTRAL,
    classes: dict[str, tuple[str, ...]] | None = None,
    interest: float = 0.0,
) -> tuple[dict[str, float], dict[str, float], float]:
    """A mensagem do aluno, antes de o mecanismo lê-la."""
    scores = {name: value for name, value in utilities.items() if value > 0.0}
    if classes:
        groups = {
            discipline: max(
                (scores[name] for name in names if name in scores), default=0.0
            )
            for discipline, names in classes.items()
        }
        groups = {name: value for name, value in groups.items() if value > 0.0}
    else:
        groups = scores
    reserve = reserve_threshold(
        selectivity=behavior.selectivity, interest=interest
    )
    return admitted_set(scores=groups, reserve=reserve), scores, reserve


def compute_bids(
    *,
    utilities: dict[str, float],
    available: list[str],
    budget: int,
    behavior: Behavior = NEUTRAL,
    classes: dict[str, tuple[str, ...]] | None = None,
    interest: float = 0.0,
) -> dict[str, int]:
    """c_{a,·}^(t,r): a estratégia do aluno no leilão."""
    groups, scores, reserve = decide(
        utilities=utilities, behavior=behavior, classes=classes, interest=interest
    )
    if not classes:
        return concave_bids(
            scores=groups, available=available, budget=budget, reserve=reserve
        )

    reachable = set(available)
    open_classes = {
        discipline: [name for name in classes[discipline] if name in reachable]
        for discipline in groups
    }
    per_group = concave_bids(
        scores=groups,
        available=[d for d, names in open_classes.items() if names],
        budget=budget,
        reserve=reserve,
    )
    bids: dict[str, int] = {}
    for discipline, credits in per_group.items():
        bids.update(
            concave_bids(
                scores=scores, available=open_classes[discipline], budget=credits
            )
        )
    return bids
