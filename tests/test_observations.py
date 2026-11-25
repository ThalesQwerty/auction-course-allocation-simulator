"""As linhas cruas que a interface recorta."""
from __future__ import annotations

import pytest

from disciplines import disciplines_from_predecessors
from profiles import single_axis
from leilao.comparison import observations_of
from leilao.config import SimulationConfig
from leilao.equations import jain_index, value_band, value_band_name
from leilao.equations._mean import mean
from leilao.simulation import run_simulation

GRADE = disciplines_from_predecessors(
    ("D1", 6, 60),
    ("D2", 6, 60),
    ("D3", 6, 60, ("D1",)),
    ("D4", 6, 60, ("D2",)),
    ("D5", 6, 60, ("D3",)),
    ("D6", 6, 60, ("D3", "D4")),
)

WORKLOAD = 180

AXES = (
    ("grade_average", 1, 0.0, 10.0),
    ("reserve", 3, 0.0, 1.0),
)


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=7,
        warmup_periods=4,
        max_residence=4,
        students_per_entry_class=3,
        rounds=3,
        max_hours=WORKLOAD,
        **single_axis(WORKLOAD),
        seed=11,
    )
    base.update(grade_cuts=(5.0, 7.0), reserve_cuts=(0.01, 0.03))
    return SimulationConfig(**{**base, **overrides})


def band_of(row, axis: str, cuts, decimals: int, low: float, high: float) -> str:
    value = getattr(row, axis)
    return value_band_name(
        band=value_band(value=value, cuts=cuts),
        cuts=cuts,
        low=low,
        high=high,
        decimals=decimals,
    )


def test_the_rows_are_the_measured_cohort_in_the_measured_periods():
    config = make_config()
    result = run_simulation(config)
    medida = {s.id for s in result.students if s.entry_period == config.warmup_periods}

    assert all(
        not period.points
        for period in result.periods
        if period.period < config.first_measured_period
    )
    for period in result.observed:
        ativos = [
            s
            for s in result.students
            if s.id in medida
            and s.entry_period <= period.period
            and (s.graduated_at or s.dismissed_at or period.period) >= period.period
        ]
        assert len(period.points) == len(ativos)
        assert all(point.period == period.period for point in period.points)


@pytest.mark.parametrize("mechanism", ["credits", "ranking"])
def test_the_raw_rows_rebuild_the_bands_the_engine_cuts(mechanism):
    """O recorte em faixas é conta de interface, não de simulação.

    Mudar um corte não pode exigir simular de novo, e para isso as linhas cruas
    têm de reproduzir, faixa por faixa, o que o motor mediria com aquele corte.
    """
    config = make_config(mechanism=mechanism)
    result = run_simulation(config)
    visto = 0

    for period in result.observed:
        for axis, decimals, low, high in AXES:
            cuts = config.band_cuts(axis)
            for snapshot in period.aggregate.by_profile[axis]:
                linhas = [
                    row
                    for row in period.points
                    if band_of(row, axis, cuts, decimals, low, high) == snapshot.group
                ]
                if snapshot.metrics is None:
                    assert not linhas
                    continue
                visto += 1
                assert len(linhas) == snapshot.metrics.students
                satisfacoes = [row.satisfaction for row in linhas]
                assert mean(satisfacoes) == pytest.approx(snapshot.metrics.satisfaction)
                assert jain_index(satisfacoes) == pytest.approx(
                    snapshot.metrics.fairness
                )
                assert mean([row.progress for row in linhas]) == pytest.approx(
                    snapshot.metrics.progress
                )
                frequencias = [
                    row.attendance for row in linhas if row.attendance is not None
                ]
                esperada = mean(frequencias) if frequencias else None
                if esperada is None:
                    assert snapshot.metrics.attendance is None
                else:
                    assert snapshot.metrics.attendance == pytest.approx(esperada)

    assert visto > 0


@pytest.mark.parametrize("mechanism", ["credits", "ranking"])
def test_the_mean_round_of_a_band_is_the_weighted_mean_of_its_students(mechanism):
    """r̄ é média por **vaga concedida**, e é por isso que a linha crua leva
    quantas o aluno ganhou: sem esse peso a faixa não reproduz a rodada média.
    """
    config = make_config(mechanism=mechanism)
    result = run_simulation(config)
    axis, decimals, low, high = AXES[0]
    cuts = config.band_cuts(axis)
    comparados = 0

    for period in result.observed:
        for snapshot in period.aggregate.by_profile[axis]:
            if snapshot.metrics is None:
                continue
            linhas = [
                row
                for row in period.points
                if band_of(row, axis, cuts, decimals, low, high) == snapshot.group
            ]
            concedidas = []
            anterior = 0
            for report in period.rounds:
                faixa = next(
                    (s for s in report.by_profile[axis] if s.group == snapshot.group),
                    None,
                )
                if faixa is None or faixa.metrics is None:
                    continue
                concedidas.append(max(0, faixa.metrics.allocated - anterior))
                anterior = faixa.metrics.allocated
            total = sum(concedidas)
            if not total:
                assert all(row.mean_round is None for row in linhas)
                continue
            do_motor = (
                sum((indice + 1) * valor for indice, valor in enumerate(concedidas))
                / total
            )
            pesos = [
                (row.won, row.mean_round)
                for row in linhas
                if row.mean_round is not None
            ]
            das_linhas = sum(peso * rodada for peso, rodada in pesos) / sum(
                peso for peso, _ in pesos
            )
            assert das_linhas == pytest.approx(do_motor)
            comparados += 1

    assert comparados > 0


@pytest.mark.parametrize("mechanism", ["credits", "ranking"])
def test_every_lifetime_figure_covers_the_same_periods(mechanism):
    """O ponto da dispersão tem de ter um denominador só.

    As quatro grandezas de vida inteira do aluno — satisfação, reserva,
    aproveitamento e rodada média — correm sobre os períodos medidos dele, e o
    de ingresso é um deles. Quando divergiam, o ponto de satisfação era média
    de um período a mais que o de aproveitamento, no mesmo aluno.
    """
    config = make_config(mechanism=mechanism)
    result = run_simulation(config)
    historico = {h.student_id: h.periods for h in result.histories}
    conferidos = 0

    for aluno in result.students:
        if aluno.entry_period != config.measured_cohort:
            continue
        vividos = [
            linha.period
            for linha in historico[aluno.id]
            if linha.period >= config.first_measured_period
        ]
        if not vividos:
            continue
        conferidos += 1
        assert aluno.measured_periods == len(vividos)
        assert aluno.mean_satisfaction == pytest.approx(
            mean(
                [
                    linha.satisfaction
                    for linha in historico[aluno.id]
                    if linha.period in vividos
                ]
            )
        )
        assert config.measured_cohort in vividos, "o ingresso tem de ser medido"

    assert conferidos > 0


def test_the_columns_of_a_run_stay_parallel():
    config = make_config()
    columns = observations_of(run_simulation(config))
    sizes = {len(values) for values in vars(columns).values()}
    assert len(sizes) == 1
    assert sizes != {0}
