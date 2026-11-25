"""Comparação entre os modelos de alocação (Seção 7.3)."""
from __future__ import annotations

import dataclasses
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .behavior import draw_interest
from .equations import (
    RequestStates,
    grade_for_attempt,
    grade_histogram,
    mean_round,
    interest_histogram,
    request_funnel,
    weighted_mean,
)
from .equations import time_to_graduate as mean_span
from .grading import GradeMeans, draw_grade_quantiles
from .config import (
    Mechanism,
    SimulationConfig,
)
from .metrics import Metrics
from .population import generate_students
from .simulation import (
    CELL_SEP,
    DisciplineSnapshot,
    GroupSnapshot,
    SimulationResult,
    run_simulation,
)

MAX_RUNS = 100

DEFAULT_WORKERS = min(4, os.cpu_count() or 1)

RunDone = Callable[["Arm", int], None]


@dataclass(frozen=True)
class Arm:
    """Um dos dois modelos comparados."""

    key: str
    mechanism: Mechanism


ARMS: tuple[Arm, ...] = (
    Arm("ranking_greedy", "ranking"),
    Arm("credits_return", "credits"),
)


ARM_BY_KEY: dict[str, Arm] = {arm.key: arm for arm in ARMS}


def arms_from_keys(keys: list[str]) -> tuple[Arm, ...]:
    """Os braços que essas chaves nomeiam, na ordem canônica de `ARM_BY_KEY`."""
    wanted = set(keys)
    unknown = sorted(wanted - ARM_BY_KEY.keys())
    if unknown:
        raise ValueError(f"braço desconhecido: {', '.join(unknown)}")
    chosen = tuple(arm for key, arm in ARM_BY_KEY.items() if key in wanted)
    if not chosen:
        raise ValueError("escolha ao menos um braço para comparar")
    return chosen


@dataclass(frozen=True)
class RulerSeries:
    """As métricas de uma simulação ao longo de **uma régua**, sem reduzir."""

    x: list[int]
    students: list[float]
    graduation_rate: list[float]
    efficiency: list[float]
    attendance: list[float | None]
    mean_round: list[float | None]
    progress: list[float]
    fidelity: list[float]
    fairness: list[float]
    grade_average: list[float]
    exclusion_rate: list[float]
    credits_supply: list[float | None]
    credits_spent: list[float | None]
    credits_returned: list[float | None]
    request_states: list[RequestStates]
    allocations_per_round: list[list[float | None]]


@dataclass(frozen=True)
class GroupSeries:
    """A `RulerSeries` de um grupo de um recorte espacial — um perfil."""

    group: str
    series: RulerSeries


RULERS: tuple[str, ...] = ("period", "age", "cohort")

CUT_AXES: tuple[str, ...] = (
    "grade_average",
    "reserve",
)


CLASS_CUTS: tuple[str, ...] = (
    "classes",
    "hours",

    "curriculum_period",
)

ELECTIVE_GROUP = "elective"


def _number_key(value: float) -> str:
    """O número como chave: sem zeros à direita e com ponto decimal, porque é"""
    return f"{value:g}"


def _class_group(snapshot: DisciplineSnapshot, axis: str) -> tuple[float, str]:
    """`(ordem, chave)` do grupo em que a turma cai, num recorte."""
    if axis == "classes":
        return (snapshot.classes, str(snapshot.classes))
    if axis == "hours":
        return (snapshot.hours, str(snapshot.hours))
    if axis == "curriculum_period":
        if snapshot.elective:
            return (float("inf"), ELECTIVE_GROUP)
        return (snapshot.curriculum_period, str(snapshot.curriculum_period))
    raise ValueError(f"recorte de turma desconhecido: {axis!r}")


@dataclass(frozen=True)
class ClassPriceSeries:
    """O preço médio da turma num grupo de um recorte da oferta, por período."""

    axis: str
    group: str
    x: list[int]
    price: list[float]


@dataclass(frozen=True)
class GroupBands:
    """Um grupo de um recorte reduzido **entre as seeds**, ponto a ponto."""

    group: str
    x: list[int]
    n: list[int]
    values: dict[str, list[tuple[float, float, float] | None]]


@dataclass(frozen=True)
class ClassPriceBands:
    """Um recorte da oferta, com os grupos dele reduzidos entre as seeds."""

    axis: str
    groups: list[GroupBands]


@dataclass(frozen=True)
class AxisBands:
    """Os grupos de um recorte sob uma régua, na ordem em que o cenário os"""

    ruler: str
    axis: str
    groups: list[GroupBands]


@dataclass(frozen=True)
class RunSummary:
    """Uma simulação reduzida a um ponto por métrica."""

    seed: int
    periods: int
    graduates: int
    dismissed: int
    population: int
    efficiency: float
    attendance: float | None
    mean_round: float | None
    progress: float
    fidelity: float
    fairness: float
    grade_average: float
    exclusion_rate: float
    request_states: RequestStates
    time_to_graduate: float | None
    allocations_per_round: list[float | None]
    allocation_seconds: list[list[float]] = field(compare=False)
    class_prices: list[ClassPriceSeries]
    by_period: RulerSeries
    by_group: dict[str, dict[str, list[GroupSeries]]]


@dataclass(frozen=True)
class ArmResult:
    """As N simulações de um braço, na ordem das seeds."""

    key: str
    mechanism: Mechanism
    runs: list[RunSummary]
    series: list[AxisBands] = field(default_factory=list)
    allocation_seconds: list[list[float]] = field(default_factory=list, compare=False)
    class_prices: list[ClassPriceBands] = field(default_factory=list)


@dataclass(frozen=True)
class ComparisonResult:
    """As N simulações de cada braço, pareadas pela seed."""

    runs: int
    arms: list[ArmResult]
    interest_distribution: list[float] = field(default_factory=list)
    grade_distribution: list[float] = field(default_factory=list)


def _within_window(result: SimulationResult, period: int | None) -> bool:
    """O evento caiu na janela medida?"""
    return period is not None and period > result.warmup_periods


def _active_in_window(result: SimulationResult) -> int:
    """Quantos alunos estiveram ativos em algum período medido."""
    if not result.observed:
        return 0
    first = result.observed[0].period
    last = result.observed[-1].period
    total = 0
    for student in result.students:
        if student.entry_period > last:
            continue
        exit_period = student.graduated_at or student.dismissed_at
        if exit_period is not None and exit_period < first:
            continue
        total += 1
    return total


def time_to_graduate(result: SimulationResult) -> float | None:
    """Períodos do ingresso ao diploma — ver `equations.time_to_graduate`."""
    return mean_span(
        s.graduated_at - s.entry_period + 1
        for s in result.students
        if _within_window(result, s.graduated_at)
    )


def allocations_per_round(result: SimulationResult) -> list[float | None]:
    """Vagas obtidas por aluno em cada rodada, na ordem delas."""
    rounds = max((len(period.rounds) for period in result.observed), default=0)
    series: list[float | None] = []
    for index in range(rounds):
        series.append(
            weighted_mean(
                [
                    (metrics.allocations_per_student, metrics.students)
                    for period in result.observed
                    if index < len(period.rounds)
                    for metrics in [period.rounds[index].overall.metrics]
                    if metrics is not None and metrics.students > 0
                ]
            )
        )
    return series


def allocation_seconds(result: SimulationResult) -> list[list[float]]:
    """Segundos do alocador em cada rodada, período a período."""
    return [
        [report.allocation_seconds for report in period.rounds]
        for period in result.periods
    ]


def mean_allocation_seconds(runs: list["RunSummary"]) -> list[list[float]]:
    """A média entre as seeds, posição a posição."""
    if not runs:
        return []
    periods = max(len(run.allocation_seconds) for run in runs)
    series: list[list[float]] = []
    for index in range(periods):
        rows = [run.allocation_seconds[index] for run in runs if index < len(run.allocation_seconds)]
        rounds = max((len(row) for row in rows), default=0)
        series.append(
            [
                sum(values) / len(values)
                for position in range(rounds)
                for values in [[row[position] for row in rows if position < len(row)]]
                if values
            ]
        )
    return series


def class_prices(result: SimulationResult) -> list[ClassPriceSeries]:
    """O preço médio da turma por recorte da oferta, período a período."""
    out: list[ClassPriceSeries] = []
    for axis in CLASS_CUTS:
        points: dict[str, dict[int, list[float]]] = {}
        order: dict[str, float] = {}
        for period in result.observed:
            for snapshot in period.disciplines:
                if snapshot.mean_price is None:
                    continue
                rank, group = _class_group(snapshot, axis)
                order[group] = rank
                points.setdefault(group, {}).setdefault(period.period, []).append(
                    snapshot.mean_price
                )
        for group in sorted(points, key=lambda name: (order[name], name)):
            periods = sorted(points[group])
            out.append(
                ClassPriceSeries(
                    axis=axis,
                    group=group,
                    x=periods,
                    price=[
                        sum(points[group][point]) / len(points[group][point])
                        for point in periods
                    ],
                )
            )
    return out


def class_price_bands(runs: list[RunSummary]) -> list[ClassPriceBands]:
    """Os quartis do preço em cada ponto, grupo a grupo."""
    out: list[ClassPriceBands] = []
    for axis in CLASS_CUTS:
        order: list[str] = []
        samples: dict[str, dict[int, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for run in runs:
            for entry in run.class_prices:
                if entry.axis != axis:
                    continue
                if entry.group not in order:
                    order.append(entry.group)
                for point, value in zip(entry.x, entry.price):
                    samples[entry.group][point].append(value)
        groups = [
            GroupBands(
                group=group,
                x=sorted(samples[group]),
                n=[len(samples[group][point]) for point in sorted(samples[group])],
                values={
                    "mean_price": [
                        _quartiles(samples[group][point])
                        for point in sorted(samples[group])
                    ]
                },
            )
            for group in order
        ]
        if groups:
            out.append(ClassPriceBands(axis=axis, groups=groups))
    return out


def weighted_states(pairs: list[tuple[Metrics, int]]) -> RequestStates:
    """A média ponderada dos seis estados, campo a campo."""
    return _mean_states(
        [(m.request_states, w) for m, w in pairs if m.request_states is not None]
    )


def _mean_states(rows: list[tuple[RequestStates, float]]) -> RequestStates:
    """A média ponderada dos seis estados, campo a campo. Saco vazio dá tudo"""
    if not rows:
        return RequestStates(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def of(field_name: str) -> float:
        return weighted_mean([(getattr(r, field_name), w) for r, w in rows]) or 0.0

    return RequestStates(
        not_eligible=of("not_eligible"),
        not_requested=of("not_requested"),
        refused=of("refused"),
        excluded=of("excluded"),
        failed=of("failed"),
        approved=of("approved"),
    )


def _measured(snapshot: GroupSnapshot | None) -> bool:
    """O recorte tem métrica: alguém, além dos calouros, disputou o instante."""
    return (
        snapshot is not None
        and snapshot.metrics is not None
        and snapshot.metrics.students > 0
    )


def _period_series(
    instants: list[tuple[int, GroupSnapshot | None, list[GroupSnapshot | None]]],
    rounds: int,
) -> RulerSeries:
    """A série de um recorte ao longo dos períodos em que ele foi medido."""
    measured = [
        (period, snapshot, by_round)
        for period, snapshot, by_round in instants
        if _measured(snapshot)
    ]

    def series(of) -> list:
        return [of(snapshot.metrics) for _, snapshot, _ in measured]

    def series_optional(of) -> list:
        """As que podem não existir no instante: o aproveitamento, que precisa"""
        return [of(snapshot.metrics) for _, snapshot, _ in measured]

    def snapshots(of) -> list:
        """As grandezas que ficam no recorte, e não em `Metrics` — as de"""
        return [of(snapshot) for _, snapshot, _ in measured]

    def saturation(by_round: list[GroupSnapshot | None]) -> list[float | None]:
        """Uma posição por rodada do cenário. Período que publicou menos"""
        row: list[float | None] = []
        for index in range(rounds):
            snapshot = by_round[index] if index < len(by_round) else None
            row.append(
                snapshot.metrics.allocations_per_student
                if _measured(snapshot)
                else None
            )
        return row

    def rounds_mean(by_round: list[GroupSnapshot | None]) -> float | None:
        """r̄ — a rodada média das vagas alocadas no período."""
        cumulative = [
            snapshot.metrics.allocated if _measured(snapshot) else None
            for snapshot in by_round
        ]
        known = [value for value in cumulative if value is not None]
        if not known:
            return None
        granted: list[int] = []
        previous = 0
        for value in known:
            granted.append(max(0, value - previous))
            previous = value
        return mean_round(allocations_per_round=granted)

    return RulerSeries(
        x=[period for period, _, _ in measured],
        students=series(lambda m: float(m.students)),
        graduation_rate=[
            snapshot.graduated / snapshot.population if snapshot.population else 0.0
            for _, snapshot, _ in measured
        ],
        efficiency=series(lambda m: m.efficiency),
        attendance=series_optional(lambda m: m.attendance),
        mean_round=[rounds_mean(by_round) for _, _, by_round in measured],
        progress=series(lambda m: m.progress),
        fidelity=series(lambda m: m.fidelity),
        fairness=series(lambda m: m.fairness),
        grade_average=series(lambda m: m.mean_grade_average),
        exclusion_rate=series(lambda m: m.exclusion_rate or 0.0),
        credits_supply=snapshots(lambda s: s.credits_per_student),
        credits_spent=snapshots(lambda s: s.mean_credits_spent),
        credits_returned=snapshots(lambda s: s.mean_credit_return),
        request_states=series(
            lambda m: m.request_states or RequestStates(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        ),
        allocations_per_round=[saturation(by_round) for _, _, by_round in measured],
    )


def _cut(report, axis: str) -> list[GroupSnapshot]:
    """Os grupos de um recorte espacial num instante."""
    return report.by_profile.get(axis, [])


def _cells(report, axis: str) -> list[GroupSnapshot]:
    """As células de um recorte espacial num instante — ver `Axis.crossed`."""
    return report.by_cohort if axis == "overall" else report.by_cell.get(axis, [])


def _cell_key(axis: str, group: str) -> tuple[str, int]:
    """`(grupo espacial, coorte)` de uma célula."""
    if axis == "overall":
        return "overall", int(group)
    spatial, _, cohort = group.rpartition(CELL_SEP)
    return spatial, int(cohort)


Instant = tuple[int, int, GroupSnapshot, list[GroupSnapshot | None]]


def _cell_instants(
    result: SimulationResult, axis: str
) -> tuple[list[str], dict[str, list[Instant]]]:
    """As células de um recorte, período a período."""
    order: list[str] = []
    out: dict[str, list[Instant]] = defaultdict(list)
    for period in result.observed:
        by_round = [
            {s.group: s for s in _cells(report, axis) if s.group is not None}
            for report in period.rounds
        ]
        for snapshot in _cells(period.aggregate, axis):
            if snapshot.group is None:
                continue
            group, cohort = _cell_key(axis, snapshot.group)
            if group not in order:
                order.append(group)
            out[group].append(
                (
                    cohort,
                    period.period,
                    snapshot,
                    [found.get(snapshot.group) for found in by_round],
                )
            )
    return order, out


def _regroup(
    instants: list[tuple[int, Instant]], *, ruler: str, rounds: int
) -> RulerSeries:
    """Reagrupa as células de um grupo numa série por ponto da régua."""
    buckets: dict[int, list[Instant]] = defaultdict(list)
    for point, instant in sorted(instants, key=lambda item: item[1][1]):
        buckets[point].append(instant)
    points = sorted(buckets)
    bags = {
        point: _period_series(
            [(period, snapshot, by_round) for _, period, snapshot, by_round in bag],
            rounds,
        )
        for point, bag in buckets.items()
    }
    points = [point for point in points if bags[point].x]

    def weighed(point: int, of) -> float:
        bag = bags[point]
        return weighted_mean(list(zip(of(bag), bag.students))) or 0.0

    def optional(point: int, of) -> float | None:
        """A mesma média ponderada, para grandeza que pode não existir."""
        bag = bags[point]
        pairs = [
            (value, weight)
            for value, weight in zip(of(bag), bag.students)
            if value is not None
        ]
        return weighted_mean(pairs) if pairs else None

    def graduation(point: int) -> float:
        bag = bags[point]
        if ruler != "cohort":
            return weighed(point, lambda s: s.graduation_rate)
        return bag.graduation_rate[-1]

    def states(point: int) -> RequestStates:
        bag = bags[point]
        return _mean_states(list(zip(bag.request_states, bag.students)))

    def saturation(point: int) -> list[float | None]:
        bag = bags[point]
        row: list[float | None] = []
        for index in range(rounds):
            pairs = [
                (values[index], weight)
                for values, weight in zip(bag.allocations_per_round, bag.students)
                if index < len(values) and values[index] is not None
            ]
            row.append(weighted_mean(pairs) if pairs else None)
        return row

    return RulerSeries(
        x=points,
        students=[sum(bags[point].students) for point in points],
        graduation_rate=[graduation(point) for point in points],
        efficiency=[weighed(point, lambda s: s.efficiency) for point in points],
        attendance=[optional(point, lambda s: s.attendance) for point in points],
        mean_round=[optional(point, lambda s: s.mean_round) for point in points],
        progress=[weighed(point, lambda s: s.progress) for point in points],
        fidelity=[weighed(point, lambda s: s.fidelity) for point in points],
        fairness=[weighed(point, lambda s: s.fairness) for point in points],
        grade_average=[weighed(point, lambda s: s.grade_average) for point in points],
        exclusion_rate=[weighed(point, lambda s: s.exclusion_rate) for point in points],
        credits_supply=[optional(point, lambda s: s.credits_supply) for point in points],
        credits_spent=[optional(point, lambda s: s.credits_spent) for point in points],
        credits_returned=[
            optional(point, lambda s: s.credits_returned) for point in points
        ],
        request_states=[states(point) for point in points],
        allocations_per_round=[saturation(point) for point in points],
    )


def group_series(
    result: SimulationResult, *, by_period: RulerSeries
) -> dict[str, dict[str, list[GroupSeries]]]:
    """As séries de cada grupo de cada recorte, régua a régua —"""
    rounds = max((len(period.rounds) for period in result.observed), default=0)
    out: dict[str, dict[str, list[GroupSeries]]] = {ruler: {} for ruler in RULERS}
    out["period"]["overall"] = [GroupSeries(group="overall", series=by_period)]

    for axis in CUT_AXES:
        order: list[str] = []
        for period in result.observed:
            for snapshot in _cut(period.aggregate, axis):
                if snapshot.group is not None and snapshot.group not in order:
                    order.append(snapshot.group)

        if not order:
            continue

        def find(report, group: str, axis: str = axis) -> GroupSnapshot | None:
            return next((s for s in _cut(report, axis) if s.group == group), None)

        out["period"][axis] = [
            GroupSeries(
                group=group,
                series=_period_series(
                    [
                        (
                            period.period,
                            find(period.aggregate, group),
                            [find(report, group) for report in period.rounds],
                        )
                        for period in result.observed
                    ],
                    rounds,
                ),
            )
            for group in order
        ]

    for axis in ("overall", *CUT_AXES):
        order, instants = _cell_instants(result, axis)
        if not order:
            continue
        for ruler in ("age", "cohort"):
            out[ruler][axis] = [
                GroupSeries(
                    group=group,
                    series=_regroup(
                        [
                            (
                                cohort if ruler == "cohort" else period - cohort,
                                instant,
                            )
                            for instant in instants[group]
                            for cohort, period, _, _ in [instant]
                        ],
                        ruler=ruler,
                        rounds=rounds,
                    ),
                )
                for group in order
            ]
    return out


STATE_KEYS: tuple[str, ...] = (
    "not_eligible",
    "not_requested",
    "refused",
    "excluded",
    "failed",
    "approved",
)

FUNNEL_KEYS: tuple[str, ...] = (
    "requested_share",
    "granted_share",
    "attended_share",
    "approved_share",
)


def _quantities(series: RulerSeries, index: int) -> dict[str, float | None]:
    """O que uma posição de uma série mede, grandeza a grandeza."""
    states = series.request_states[index]
    values: dict[str, float | None] = {
        "students": float(series.students[index]),
        "graduation_rate": series.graduation_rate[index],
        "efficiency": series.efficiency[index],
        "attendance": series.attendance[index],
        "mean_round": series.mean_round[index],
        "progress": series.progress[index],
        "fidelity": series.fidelity[index],
        "fairness": series.fairness[index],
        "grade_average": series.grade_average[index],
        "exclusion_rate": series.exclusion_rate[index],
        "credits_supply": series.credits_supply[index],
        "credits_spent": series.credits_spent[index],
        "credits_returned": series.credits_returned[index],
    }
    for key in STATE_KEYS:
        values[key] = getattr(states, key)
    funnel = request_funnel(states)
    for key in FUNNEL_KEYS:
        values[key] = getattr(funnel, key)
    for r, value in enumerate(series.allocations_per_round[index], start=1):
        values[f"round_{r}"] = value
    return values


def _quartiles(values: list[float]) -> tuple[float, float, float]:
    """`(q1, mediana, q3)` por interpolação linear — o método 7, o mesmo do"""
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    return (round(float(q1), 4), round(float(median), 4), round(float(q3), 4))


def _group_bands(group: str, samples: list[RulerSeries]) -> GroupBands:
    """Reduz as séries de um grupo, uma por seed, a quartis por ponto da"""
    by_point: dict[int, list[dict[str, float | None]]] = defaultdict(list)
    for series in samples:
        for index, point in enumerate(series.x):
            by_point[point].append(_quantities(series, index))
    points = sorted(by_point)
    keys: list[str] = []
    for point in points:
        for row in by_point[point]:
            keys.extend(k for k in row if k not in keys)

    def band(point: int, key: str) -> tuple[float, float, float] | None:
        values = [row[key] for row in by_point[point] if row.get(key) is not None]
        return _quartiles(values) if values else None

    return GroupBands(
        group=group,
        x=points,
        n=[len(by_point[point]) for point in points],
        values={key: [band(point, key) for point in points] for key in keys},
    )


def bands(runs: list[RunSummary]) -> list[AxisBands]:
    """As séries de um braço reduzidas entre as seeds, régua por recorte."""
    out: list[AxisBands] = []
    for ruler in RULERS:
        for axis in ("overall", *CUT_AXES):
            order: list[str] = []
            samples: dict[str, list[RulerSeries]] = defaultdict(list)
            for run in runs:
                for entry in run.by_group.get(ruler, {}).get(axis, []):
                    if entry.group not in order:
                        order.append(entry.group)
                    samples[entry.group].append(entry.series)
            if not order:
                continue
            out.append(
                AxisBands(
                    ruler=ruler,
                    axis=axis,
                    groups=[_group_bands(group, samples[group]) for group in order],
                )
            )
    return out


def summarize(result: SimulationResult, *, seed: int) -> RunSummary:
    """Reduz uma simulação inteira a um ponto por métrica."""
    graduates = sum(1 for s in result.students if _within_window(result, s.graduated_at))
    dismissed = sum(1 for s in result.students if _within_window(result, s.dismissed_at))
    rounds = max((len(period.rounds) for period in result.observed), default=0)
    by_period = _period_series(
        [
            (
                period.period,
                period.aggregate.overall,
                [report.overall for report in period.rounds],
            )
            for period in result.observed
        ],
        rounds,
    )
    weights = by_period.students

    def mean(values: list[float]) -> float:
        return weighted_mean(list(zip(values, weights))) or 0.0

    states = [
        (metrics, metrics.students)
        for period in result.observed
        for metrics in [period.aggregate.overall.metrics]
        if _measured(period.aggregate.overall)
    ]

    return RunSummary(
        seed=seed,
        periods=len(result.observed),
        graduates=graduates,
        dismissed=dismissed,
        population=_active_in_window(result),
        efficiency=mean(by_period.efficiency),
        attendance=mean([v for v in by_period.attendance if v is not None]),
        mean_round=mean([v for v in by_period.mean_round if v is not None]),
        progress=mean(by_period.progress),
        fidelity=mean(by_period.fidelity),
        fairness=mean(by_period.fairness),
        grade_average=mean(by_period.grade_average),
        exclusion_rate=mean(by_period.exclusion_rate),
        request_states=weighted_states(states),
        time_to_graduate=time_to_graduate(result),
        allocations_per_round=allocations_per_round(result),
        allocation_seconds=allocation_seconds(result),
        class_prices=class_prices(result),
        by_period=by_period,
        by_group=group_series(result, by_period=by_period),
    )


SAMPLE_SEED = 1


def sample_interest_distribution(config: SimulationConfig) -> list[float]:
    """O histograma de interesse do cenário, sorteado à parte da simulação."""
    students = generate_students(config, np.random.default_rng(SAMPLE_SEED))
    rows = draw_interest(students, config, np.random.default_rng(SAMPLE_SEED))
    return interest_histogram(rows.values())


def sample_grade_distribution(config: SimulationConfig) -> list[float]:
    """O histograma de notas de primeira tentativa, pelo mesmo motivo e do mesmo"""
    students = generate_students(config, np.random.default_rng(SAMPLE_SEED))
    quantiles = draw_grade_quantiles(
        students, config.disciplines, config, np.random.default_rng(SAMPLE_SEED)
    )
    mean = GradeMeans().of(config, 0)
    grades = [
        grade_for_attempt(
            quantile=quantile, grade_mean=mean, grade_sd=config.grade_sd
        )
        for (_, _, attempt), quantile in quantiles.items()
        if attempt == 0
    ]
    return grade_histogram(grades)


def arm_config(config: SimulationConfig, *, arm: Arm, seed: int) -> SimulationConfig:
    """O cenário como um braço o roda: as quatro escolhas do braço e a seed."""
    return dataclasses.replace(
        config,
        mechanism=arm.mechanism,
        seed=seed,
    )


def _run_one(config: SimulationConfig, arm: Arm, seed: int) -> RunSummary:
    return summarize(
        run_simulation(arm_config(config, arm=arm, seed=seed), keep_histories=False),
        seed=seed,
    )


def _run_arms(
    config: SimulationConfig,
    *,
    arms: tuple[Arm, ...],
    seeds: list[int],
    workers: int,
    on_run_done: RunDone | None,
) -> list[list[RunSummary]]:
    """As `len(arms) × len(seeds)` simulações, na ordem em que foram pedidas."""
    if workers <= 1:
        done: list[list[RunSummary]] = []
        for arm in arms:
            summaries: list[RunSummary] = []
            for seed in seeds:
                summaries.append(_run_one(config, arm, seed))
                if on_run_done is not None:
                    on_run_done(arm, seed)
            done.append(summaries)
        return done

    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = [
            [pool.submit(_run_one, config, arm, seed) for seed in seeds] for arm in arms
        ]
        if on_run_done is not None:
            where = {
                job: (arm, seed)
                for arm, arm_jobs in zip(arms, jobs)
                for seed, job in zip(seeds, arm_jobs)
            }
            for job in as_completed(where):
                on_run_done(*where[job])
        return [[job.result() for job in arm_jobs] for arm_jobs in jobs]


def run_comparison(
    config: SimulationConfig,
    *,
    runs: int,
    workers: int = DEFAULT_WORKERS,
    arms: tuple[Arm, ...] = ARMS,
    on_run_done: RunDone | None = None,
) -> ComparisonResult:
    """Roda `runs` simulações em cada braço, com as seeds de 1 a `runs`."""
    if not 1 <= runs <= MAX_RUNS:
        raise ValueError(f"o número de simulações deve estar entre 1 e {MAX_RUNS}")
    seeds = list(range(1, runs + 1))
    jobs = _run_arms(
        config, arms=arms, seeds=seeds, workers=workers, on_run_done=on_run_done
    )
    return ComparisonResult(
        runs=runs,
        interest_distribution=sample_interest_distribution(config),
        grade_distribution=sample_grade_distribution(config),
        arms=[
            ArmResult(
                key=arm.key,
                mechanism=arm.mechanism,
                        runs=summaries,
                series=bands(summaries),
                allocation_seconds=mean_allocation_seconds(summaries),
                class_prices=class_price_bands(summaries),
            )
            for arm, summaries in zip(arms, jobs)
        ],
    )
