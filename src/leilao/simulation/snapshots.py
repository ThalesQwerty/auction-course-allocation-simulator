"""Como um instante da simulação vira linhas de relatório."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from ..config import SimulationConfig
from ..equations import (
    RequestStates,
    credits_per_seat,
    demand_counts,
    demand_intensity,
    progress,
    request_states,
    semestralization,
    attendance,
    value_band,
    value_band_name,
    value_band_names,
)
from ..equations._mean import mean
from ..metrics import compute_metrics
from ..population import Student
from .reports import GroupSnapshot


CELL_SEP = "|"

OUTSIDE = "\x00fora"


def measured_students(
    *, config: SimulationConfig, students: list[Student], period: int
) -> list[Student]:
    """Quem entra nas médias de um período: só as coortes observadas.

    Sem coorte observada entra todo mundo menos o calouro.
    """
    if config.measured_cohorts:
        return [s for s in students if config.measures(s.entry_period)]
    return [s for s in students if s.entry_period != period]


@dataclass(frozen=True)
class Axis:
    """Como rotular cada aluno e em que ordem as séries saem."""

    key: Callable[[Student, "Measurements"], str]
    order: list[str]
    partitions: bool = True

    @classmethod
    def crossed(cls, spatial: "Axis", cohort: "Axis") -> "Axis":
        """O produto de um recorte espacial pela coorte — a **célula**."""
        return cls(
            key=lambda s, v: (
                OUTSIDE
                if spatial.key(s, v) == OUTSIDE
                else f"{spatial.key(s, v)}{CELL_SEP}{cohort.key(s, v)}"
            ),
            order=[
                f"{group}{CELL_SEP}{entry}"
                for group in spatial.order
                for entry in cohort.order
            ],
            partitions=spatial.partitions and cohort.partitions,
        )

    @classmethod
    def cohorts(cls, entry_periods: list[int], period: int) -> "Axis":
        """O eixo das coortes até o período corrente."""
        return cls(
            key=lambda s, v: str(s.entry_period),
            order=[str(entry) for entry in entry_periods if entry <= period],
        )

    @classmethod
    def states(cls, config: SimulationConfig) -> dict[str, "Axis"]:
        """Os eixos de **estado**, cortados em faixas de valor corrente."""
        axes = {
            "grade_average": _state_axis(
                config, "grade_average", lambda v: v.grade_averages, decimals=1
            ),
            "demand": _state_axis(
                config, "demand", lambda v: v.demands, decimals=2
            ),
        }
        return axes


def _state_axis(
    config: SimulationConfig,
    axis: str,
    source: Callable[["Measurements"], dict[str, float]],
    *,
    decimals: int,
) -> Axis:
    """Um eixo de estado: rotula pelo valor medido, com os cortes do cenário."""
    cuts = config.band_cuts(axis)
    low, high = config.band_domain(axis)
    order = value_band_names(cuts=cuts, low=low, high=high, decimals=decimals)

    def key(student: Student, values: "Measurements") -> str:
        measured = source(values)
        if student.id not in measured:
            return OUTSIDE
        return value_band_name(
            band=value_band(value=measured[student.id], cuts=cuts),
            cuts=cuts,
            low=low,
            high=high,
            decimals=decimals,
        )

    return Axis(key=key, order=order, partitions=False)


@dataclass(frozen=True)
class Measurements:
    """As grandezas por aluno de um instante, já calculadas."""

    satisfactions: dict[str, float]
    progresses: dict[str, float]
    grade_averages: dict[str, float]
    semestralizations: dict[str, float]
    scarcities: dict[str, float]
    contentions: dict[str, float]
    approved_hours: dict[str, int]
    won: dict[str, set[str]]
    excluded: dict[str, list[str]] | None
    attendances: dict[str, float | None] | None
    selectivities: dict[str, float]
    reserves: dict[str, float]
    eligible_disciplines: dict[str, int]
    requested_disciplines: dict[str, int]
    demands: dict[str, float]
    request_states: dict[str, RequestStates] | None
    credits: dict[str, int]
    supply: dict[str, int]
    bids: dict[str, int]
    credit_returns: dict[str, int] | None


def measure(
    *,
    config: SimulationConfig,
    active: list[Student],
    satisfactions: dict[str, float],
    grade_averages: dict[str, float],
    scarcities: dict[str, float],
    contentions: dict[str, float],
    won: dict[str, set[str]],
    messages: dict[str, dict[str, float]],
    utilities: dict[str, dict[str, float]],
    credits: dict[str, int],
    supply: dict[str, int],
    bids: dict[str, int],
    ages: dict[str, int],
    hours: dict[str, int],
    discipline_hours: dict[str, int],
    credit_returns: dict[str, int] | None,
    selectivities: dict[str, float] | None = None,
    reserves: dict[str, float] | None = None,
    allocated_satisfactions: dict[str, float] | None = None,
    retained: dict[str, set[str]] | None = None,
    excluded: dict[str, list[str]] | None = None,
    requested: dict[str, set[str]] | None = None,
) -> Measurements:
    """Calcula as grandezas que dependem do instante."""
    approved = {s.id: s.approved(config.min_grade) for s in active}
    approved_hours = {
        student_id: sum(discipline_hours[name] for name in names)
        for student_id, names in approved.items()
    }
    elective_hours_of = config.elective_hours_by_discipline()
    approved_elective_hours = {
        student_id: sum(
            discipline_hours[name] for name in names if name in elective_hours_of
        )
        for student_id, names in approved.items()
    }
    required_hours = sum(
        discipline_hours[name] for name in config.required_disciplines()
    )
    discipline_of = config.discipline_by_class()
    seats_of = config.seats_by_class()
    counts = {
        s.id: demand_counts(
            eligible=utilities[s.id],
            requested=requested[s.id] if requested is not None else (),
            groups=discipline_of,
            seats=seats_of,
        )
        for s in active
    }
    return Measurements(
        satisfactions=satisfactions,
        progresses={
            s.id: progress(
                approved_required_hours=approved_hours[s.id]
                - approved_elective_hours[s.id],
                approved_elective_hours=approved_elective_hours[s.id],
                required_hours=required_hours,
                elective_hours_needed=config.elective_hours,
            )
            for s in active
        },
        grade_averages=grade_averages,
        semestralizations={
            s.id: semestralization(
                approved_hours=approved_hours[s.id],
                max_hours=config.max_hours,
                periods_completed=ages[s.id],
            )
            for s in active
        },
        scarcities=scarcities,
        contentions=contentions,
        approved_hours=approved_hours,
        won=won,
        excluded=excluded,
        attendances=(
            {
                s.id: attendance(
                    won=won[s.id], attended=retained[s.id], hours=hours
                )
                for s in active
            }
            if retained is not None
            else None
        ),
        request_states=(
            {
                s.id: request_states(
                    catalogue=[d.name for d in config.disciplines],
                    approved=s.approved(config.min_grade),
                    eligible=utilities[s.id],
                    requested=requested[s.id],
                    won=won[s.id],
                    retained=retained[s.id],
                    groups=discipline_of,
                )
                for s in active
            }
            if retained is not None and requested is not None
            else None
        ),
        selectivities=selectivities or {s.id: 0.0 for s in active},
        reserves=reserves or {s.id: 0.0 for s in active},
        eligible_disciplines={s.id: counts[s.id][0] for s in active},
        requested_disciplines={s.id: counts[s.id][1] for s in active},
        demands={
            s.id: demand_intensity(
                eligible=counts[s.id][0], requested=counts[s.id][1]
            )
            or 0.0
            for s in active
        },
        credits=credits,
        supply=supply,
        bids=bids,
        credit_returns=credit_returns,
    )


def snapshot(
    *,
    group: str | None,
    members: list[Student],
    measured: list[Student],
    values: Measurements,
    total_seats: int,
    population: int | None,
    graduated: int | None,
    dismissed: int | None,
    uses_credits: bool,
) -> GroupSnapshot:
    """Um recorte qualquer: a universidade inteira ou uma coorte."""
    if not measured:
        return GroupSnapshot(
            group=group,
            metrics=None,
            active=len(members),
            population=population,
            graduated=graduated,
            dismissed=dismissed,
            mean_credits=None,
            mean_approved_hours=None,
            credits_per_student=None,
            credits_per_seat=None,
            mean_bids=None,
            mean_credits_spent=None,
            mean_credit_return=None,
        )

    ids = [s.id for s in measured]
    supply = sum(values.supply[i] for i in ids)

    def pick(source: dict[str, float]) -> list[float]:
        return [source[i] for i in ids]

    def in_credits(value: float) -> float | None:
        """Grandeza de crédito: `None` onde não há moeda."""
        return value if uses_credits else None

    return GroupSnapshot(
        group=group,
        metrics=compute_metrics(
            satisfactions=pick(values.satisfactions),

            progresses=pick(values.progresses),
            grade_averages=pick(values.grade_averages),
            semestralizations=pick(values.semestralizations),
            scarcities=pick(values.scarcities),
            contentions=pick(values.contentions),
            allocated=sum(len(values.won[i]) for i in ids),
            total_seats=total_seats,


            excluded=(
                sum(len(values.excluded[i]) for i in ids)
                if values.excluded is not None
                else None
            ),
            attendances=(
                pick(values.attendances)
                if values.attendances is not None
                else None
            ),
            states=(
                [values.request_states[i] for i in ids]
                if values.request_states is not None
                else None
            ),
        ),
        active=len(members),
        population=population,
        graduated=graduated,
        dismissed=dismissed,
        mean_credits=in_credits(mean(pick(values.credits))),
        mean_approved_hours=mean(pick(values.approved_hours)),
        credits_per_student=in_credits(supply / len(ids)),
        credits_per_seat=(
            credits_per_seat(supply=supply, total_seats=total_seats)
            if uses_credits
            else None
        ),
        mean_bids=in_credits(mean(pick(values.bids))),
        mean_credits_spent=in_credits(
            (supply - sum(values.credits[i] for i in ids)) / len(ids)
        ),
        mean_credit_return=(
            mean([values.credit_returns[i] for i in ids])
            if uses_credits and values.credit_returns is not None
            else None
        ),
    )


def snapshot_groups(
    *,
    config: SimulationConfig,
    active: list[Student],
    students: list[Student],
    period: int,
    axes: dict[str, Axis],
    values: Measurements,
    total_seats: int,
) -> tuple[GroupSnapshot, dict[str, list[GroupSnapshot]]]:
    """O agregado da universidade e o recorte de cada eixo, no mesmo instante."""

    def measured_of(students_: list[Student]) -> list[Student]:
        return measured_students(config=config, students=students_, period=period)

    def take(
        group: str | None,
        members: list[Student],
        population: int | None,
        graduated: int | None,
        dismissed: int | None,
    ):
        return snapshot(
            group=group,
            members=members,
            measured=measured_of(members),
            values=values,
            total_seats=total_seats,
            population=population,
            graduated=graduated,
            dismissed=dismissed,
            uses_credits=config.uses_credits,
        )

    entered = (
        [s for s in students if config.measures(s.entry_period)]
        if config.measured_cohorts
        else [s for s in students if s.entry_period <= period]
    )
    overall = take(
        None,
        active,
        len(entered),
        sum(1 for s in entered if s.graduated_at is not None),
        sum(1 for s in entered if s.dismissed_at is not None),
    )

    def split(axis: Axis) -> list[GroupSnapshot]:
        members: dict[str, list[Student]] = {key: [] for key in axis.order}
        labelled = active if axis.partitions else measured_of(active)
        for student in labelled:
            label = axis.key(student, values)
            if label in members:
                members[label].append(student)
        if not axis.partitions:
            return [take(key, members[key], None, None, None) for key in axis.order]
        population = Counter(axis.key(s, values) for s in entered)
        graduated = Counter(
            axis.key(s, values) for s in entered if s.graduated_at is not None
        )
        dismissed = Counter(
            axis.key(s, values) for s in entered if s.dismissed_at is not None
        )
        return [
            take(key, members[key], population[key], graduated[key], dismissed[key])
            for key in axis.order
        ]

    return overall, {name: split(axis) for name, axis in axes.items()}
