"""A linha de base por CR (Seção 7.3.1, eqs. 49-50) e a comparação entre os"""
import dataclasses
from collections import Counter

import numpy as np
import pytest

from leilao.behavior import DISTRIBUTION_BINS
from leilao.grading import DISTRIBUTION_BINS as GRADE_BINS
from leilao.equations import value_band_names
from leilao.comparison import (
    ARMS,
    MAX_RUNS,
    allocations_per_round,
    bands,
    run_comparison,
    summarize,
)
from leilao.equations import weighted_mean
from profiles import single_axis
from disciplines import disciplines_from_predecessors
from leilao.config import (
    Discipline,
    SimulationConfig,
)
from leilao.equations import serial_dictatorship
from leilao.ranking import allocate_by_ilp, allocate_by_ranking, request_set
from leilao.simulation import GUARANTEED_ROUND, run_simulation

GRADE = disciplines_from_predecessors(
    ("D1", 6, 60),
    ("D2", 6, 60),
    ("D3", 4, 60, ("D1",)),
    ("D4", 4, 90, ("D2",)),
    ("D5", 3, 60, ("D3",)),
)

WORKLOAD = 180
HOURS = {d.name: d.hours for d in GRADE}


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=6,
        students_per_entry_class=3,
        rounds=2,
        max_hours=WORKLOAD,
        **single_axis(WORKLOAD),
        mechanism="ranking",
        seed=11,
    )
    return SimulationConfig(**{**base, **overrides})


def ask(utilities, available=None, capacity=WORKLOAD, **kwargs):
    return request_set(
        utilities=utilities,
        available=list(utilities) if available is None else available,
        hours=HOURS,
        capacity=capacity,
        **kwargs,
    )


def test_the_request_fits_the_workload_ex_ante():
    """A auto-restrição que o trabalho aponta como a primeira deficiência do"""
    utilities = {"D1": 0.3, "D2": 0.25, "D3": 0.2, "D4": 0.15, "D5": 0.1}
    wanted = ask(utilities)
    assert wanted == ["D1", "D2", "D3"]
    assert sum(HOURS[name] for name in wanted) <= WORKLOAD


def test_the_request_is_a_knapsack_and_not_an_ordering():
    """A ordenação por utilidade erra assim que as cargas diferem: com 120 h de"""
    utilities = {"D1": 0.25, "D2": 0.25, "D4": 0.40}
    assert ask(utilities, capacity=120) == ["D1", "D2"]


def test_the_request_covers_only_what_is_available_and_wanted():
    utilities = {"D1": 0.6, "D2": 0.0, "D3": 0.4}
    assert ask(utilities, available=["D1", "D3"]) == ["D1", "D3"]
    assert ask(utilities) == ["D1", "D3"]
    assert ask({"D1": 0.5}, available=[]) == []


def test_a_tie_in_the_request_fills_the_workload():
    """Empatadas as utilidades, qual trinca sai é indiferente e o solver escolhe
    uma delas. O que se exige é o valor ótimo, que aqui é encher a carga.
    """
    tied = {"D2": 0.25, "D1": 0.25, "D5": 0.25, "D3": 0.25}
    pedido = ask(tied)
    assert len(pedido) == 3
    assert set(pedido) <= set(tied)
    assert sum(HOURS[name] for name in pedido) == WORKLOAD
    assert ask(tied) == pedido


def test_the_higher_grade_average_takes_the_last_seat():
    granted = allocate_by_ranking(
        requests=[("baixo", "D5"), ("alto", "D5")],
        priority={"baixo": 6.0, "alto": 8.5},
        seats={"D5": 1},
        hours=HOURS,
        capacity={"baixo": WORKLOAD, "alto": WORKLOAD},
    )
    assert granted == [("alto", "D5")]


def test_the_student_loses_what_he_wanted_least_when_the_workload_binds():
    """A guarda de carga da caminhada: o pedido da eq. (50) já cabe em W_a, mas"""
    granted = allocate_by_ranking(
        requests=[("a", "D1"), ("a", "D2"), ("a", "D3")],
        priority={"a": 7.0},
        seats={"D1": 5, "D2": 5, "D3": 5},
        hours=HOURS,
        capacity={"a": 120},
    )
    assert granted == [("a", "D1"), ("a", "D2")]


def test_the_ilp_respects_the_workload_and_the_seats():
    granted = allocate_by_ilp(
        requests=[("a", "D1"), ("a", "D2"), ("a", "D3")],
        priority={"a": 7.0},
        seats={"D1": 5, "D2": 5, "D3": 5},
        hours=HOURS,
        capacity={"a": 120},
    )
    assert len(granted) == 2
    assert all(student == "a" for student, _ in granted)


def test_the_tiebreak_decides_only_among_equals():
    """O ε desempata quem tem o mesmo CR, e é o lado que **lê** o desempate: a"""
    granted = serial_dictatorship(
        requests=[("a1", "x1"), ("a2", "x1"), ("a3", "x1")],
        priority={"a1": 7.0, "a2": 7.0, "a3": 7.0},
        seats={"x1": 2},
        hours={"x1": 60},
        capacity={"a1": 60, "a2": 60, "a3": 60},
        tiebreak={"a1": 0.1, "a2": 0.7, "a3": 0.4},
    )
    assert sorted(student for student, _ in granted) == ["a2", "a3"]


def test_the_baseline_runs_and_respects_the_seats():
    result = run_simulation(make_config())
    for period in result.periods:
        for snapshot in period.disciplines:
            assert snapshot.filled <= snapshot.seats


def test_the_baseline_respects_the_workload_cap():
    """eq. (4): a carga obtida no período nunca passa de W_a. Aqui ela é"""
    result = run_simulation(make_config())
    hours = {d.name: d.hours for d in GRADE}
    for history in result.histories:
        for record in history.periods:
            won = [r for r in record.requests if r.won_round is not None]
            assert sum(hours[r.discipline] for r in won) <= WORKLOAD


def test_the_baseline_has_no_credits_anywhere():
    """Sem leilão não há orçamento, preço nem retorno — e as grandezas saem"""
    result = run_simulation(make_config())
    for period in result.periods:
        assert period.aggregate.prices is None
        for snapshot in period.disciplines:
            assert snapshot.mean_price is None
        for report in [period.aggregate, *period.rounds]:
            for group in [report.overall, *report.by_cohort]:
                assert group.mean_credits is None
                assert group.credits_per_student is None
                assert group.credits_per_seat is None
                assert group.mean_bids is None
                assert group.mean_credit_return is None


def test_the_baseline_still_grants_the_entrants_their_entry_seats():
    """A matrícula garantida é do modelo da universidade, não do mecanismo:"""
    result = run_simulation(make_config())
    first = result.histories[0].periods[0]
    granted = [r for r in first.requests if r.won_round == GUARANTEED_ROUND]
    assert {r.discipline for r in granted} == {"D1", "D2"}
    assert all(r.paid == 0 for r in granted)


def test_the_baseline_is_deterministic():
    first = run_simulation(make_config())
    second = run_simulation(make_config())
    assert first.periods[-1].aggregate.overall == second.periods[-1].aggregate.overall


def test_the_two_mechanisms_start_from_the_same_population():
    """A condição metodológica da Seção 7.3: mesma seed, mesma inicialização."""
    credits = run_simulation(make_config(mechanism="credits"))
    ranking = run_simulation(make_config(mechanism="ranking"))
    assert [s.name for s in credits.students] == [s.name for s in ranking.students]
    assert [s.entry_period for s in credits.students] == [
        s.entry_period for s in ranking.students
    ]


def test_the_two_mechanisms_allocate_differently():
    credits = run_simulation(make_config(mechanism="credits"))
    ranking = run_simulation(make_config(mechanism="ranking"))
    assert credits.periods[-1].aggregate.overall.metrics != (
        ranking.periods[-1].aggregate.overall.metrics
    )


def test_the_comparison_pairs_the_seeds_across_every_arm():
    result = run_comparison(make_config(), runs=3)
    assert result.runs == 3
    assert [arm.key for arm in result.arms] == [arm.key for arm in ARMS]
    for arm in result.arms:
        assert [r.seed for r in arm.runs] == [1, 2, 3]


def test_the_comparison_ignores_the_scenario_seed():
    """Numa comparação a seed deixa de ser parâmetro e vira o eixo da amostra."""
    first = run_comparison(make_config(seed=1), runs=2)
    second = run_comparison(make_config(seed=999), runs=2)
    assert first == second
    assert first.interest_distribution and first.grade_distribution


def test_the_comparison_carries_both_scenario_distributions():
    """Os dois histogramas de entrada vêm com a comparação, para a tela mostrar"""
    result = run_comparison(make_config(), runs=2)
    assert len(result.interest_distribution) == DISTRIBUTION_BINS
    assert len(result.grade_distribution) == GRADE_BINS
    assert sum(result.interest_distribution) == pytest.approx(1.0)
    assert sum(result.grade_distribution) == pytest.approx(1.0)

    wider = run_comparison(make_config(interest_sigma=3.0), runs=2)
    assert wider.grade_distribution == result.grade_distribution
    assert wider.interest_distribution != result.interest_distribution


def test_the_comparison_rejects_a_run_count_out_of_range():
    with pytest.raises(ValueError):
        run_comparison(make_config(), runs=0)


def test_the_summary_weights_the_periods_by_the_active_students():
    """A média ponderada tem de cair entre o menor e o maior valor por período"""
    result = run_simulation(make_config())
    summary = summarize(result, seed=7)
    efficiencies = [
        p.aggregate.overall.metrics.satisfaction
        for p in result.periods
        if p.aggregate.overall.metrics
    ]
    assert min(efficiencies) <= summary.satisfaction <= max(efficiencies)
    assert summary.periods == len(result.periods)


def test_the_series_by_period_is_the_material_of_the_weighted_mean():
    """As duas leituras saem do mesmo lugar: a média ponderada do que está em"""
    result = run_simulation(make_config())
    summary = summarize(result, seed=7)
    series = summary.by_period

    lengths = {
        len(series.x),
        len(series.students),
        len(series.satisfaction),
        len(series.attendance),
        len(series.fairness),
        len(series.mean_round),
    }
    assert lengths == {len(series.x)}
    assert series.x

    assert 1 not in series.x
    assert series.x == sorted(series.x)

    recomputed = weighted_mean(list(zip(series.satisfaction, series.students)))
    assert recomputed == pytest.approx(summary.satisfaction)


MIXED = dict(
    students_per_entry_class=1,
    selectivity_mean=-1.6,
)


@pytest.mark.parametrize("axis", ["grade_average", "demand"])
def test_each_cut_partitions_the_aggregate_period_by_period(axis):
    """Em cada período, os grupos de um recorte somados com o peso deles"""
    result = run_simulation(make_config(**MIXED, grade_cuts=(5.0,), demand_cuts=(0.5,)))

    medidos = 0
    for period in result.observed:
        overall = period.aggregate.overall
        if overall.metrics is None:
            continue
        groups = [s for s in period.aggregate.by_profile[axis] if s.metrics]
        assert groups
        medidos += 1
        assert sum(g.metrics.students for g in groups) == overall.metrics.students
        for name in ("satisfaction", "progress"):
            recomposed = weighted_mean(
                [(getattr(g.metrics, name), g.metrics.students) for g in groups]
            )
            assert recomposed == pytest.approx(getattr(overall.metrics, name)), name
    assert medidos


def test_the_quantile_bands_come_out_from_the_lowest_to_the_highest():
    """As faixas saem sempre na mesma ordem — a da legenda, em qualquer"""
    config = make_config(**MIXED, grade_cuts=(5.0, 7.0), demand_cuts=(0.25, 0.75))
    result = run_simulation(config)
    summary = summarize(result, seed=3)

    esperado = {
        "grade_average": value_band_names(cuts=(5.0, 7.0), low=0.0, high=10.0),
        "demand": value_band_names(
            cuts=(0.25, 0.75), low=0.0, high=1.0, decimals=2
        ),
    }
    assert "credits" not in summary.by_group["period"]
    for period in result.observed:
        for axis, nomes in esperado.items():
            assert [s.group for s in period.aggregate.by_profile[axis]] == nomes


def test_the_graduation_rate_is_cumulative_over_who_entered():
    """A fração de concluintes por período é acumulada: quem já concluiu até"""
    result = run_simulation(make_config())
    summary = summarize(result, seed=3)

    rates = summary.by_period.graduation_rate
    assert rates
    assert all(0.0 <= rate <= 1.0 for rate in rates)

    last = result.periods[-1].aggregate.overall
    if summary.by_period.x and summary.by_period.x[-1] == result.periods[-1].period:
        assert summary.by_period.graduation_rate[-1] == pytest.approx(
            last.graduated / last.population
        )


def test_the_bands_reduce_the_seeds_to_quartiles():
    """A faixa de um braço é `(q1, mediana, q3)` entre as seeds, ponto a"""
    summaries = [summarize(run_simulation(make_config(seed=seed)), seed=seed) for seed in (1, 2, 3)]
    axes = bands(summaries)

    assert [a.axis for a in axes] == ["overall"]
    overall = axes[0].groups[0]
    for index, period in enumerate(overall.x):
        values = [
            s.by_period.satisfaction[s.by_period.x.index(period)]
            for s in summaries
            if period in s.by_period.x
        ]
        assert overall.n[index] == len(values)
        q1, median, q3 = overall.values["satisfaction"][index]
        assert q1 <= median <= q3
        assert median == pytest.approx(float(np.median(values)), abs=1e-4)


def test_the_saturation_by_period_reduces_to_the_aggregate_one():
    """A saturação por período e a agregada são a mesma grandeza em dois"""
    config = make_config(rounds=3)
    result = run_simulation(config)
    summary = summarize(result, seed=11)
    series = summary.by_period

    assert all(1 <= len(row) <= 3 for row in series.allocations_per_round)

    for index, aggregate in enumerate(summary.allocations_per_round):
        pairs = [
            (row[index], weight)
            for row, weight in zip(series.allocations_per_round, series.students)
            if index < len(row) and row[index] is not None
        ]
        assert weighted_mean(pairs) == pytest.approx(aggregate)


def test_the_series_by_period_carries_the_weight_of_each_point():
    """O peso de cada ponto é quantos alunos ele mediu, e é o teste de"""
    result = run_simulation(make_config())
    students = summarize(result, seed=1).by_period.students

    assert len(students) == len(result.observed) - 1
    assert all(count > 0 for count in students)


def test_the_saturation_has_one_figure_per_round_and_decays():
    """Uma posição por rodada **corrida**: o período para quando uma rodada"""
    config = make_config(rounds=3)
    series = allocations_per_round(run_simulation(config))

    assert 1 <= len(series) <= 3
    assert all(value is not None for value in series)
    assert series == sorted(series, reverse=True)
    assert series[-1] == 0.0 or len(series) == 3


def test_the_saturation_sums_to_the_allocation_of_the_period():
    """Somadas, as rodadas dão as vagas por aluno do período — é a mesma"""
    result = run_simulation(make_config(rounds=2))

    for period in result.periods:
        aggregate = period.aggregate.overall.metrics
        if aggregate is None:
            continue
        by_round = [
            report.overall.metrics.allocated
            for report in period.rounds
            if report.overall.metrics is not None
        ]
        assert sum(by_round) == aggregate.allocated


def test_the_saturation_is_measured_in_both_mechanisms():
    """A linha de base também tem rodadas: o aluno refaz a mochila com a carga"""
    for mechanism in ("credits", "ranking"):
        series = allocations_per_round(
            run_simulation(make_config(mechanism=mechanism, rounds=2))
        )
        assert len(series) == 2
        assert series[0] > 0


def test_the_summary_survives_a_simulation_with_no_active_students():
    """Guarda: sem período publicado não há média a tirar, e o resumo sai zerado"""
    empty = dataclasses.replace(run_simulation(make_config()), periods=[])
    assert summarize(empty, seed=1).satisfaction == 0.0
