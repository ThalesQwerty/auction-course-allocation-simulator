"""A linha de base por CR (Seção 7.3.1, eqs. 49-50) e a comparação entre os
dois mecanismos (Seção 7.3)."""
import dataclasses

import pytest

from leilao.comparison import ARMS, allocations_per_round, run_comparison, summarize
from leilao.config import AffinityProfile, Discipline, SimulationConfig
from leilao.ranking import allocate_by_ranking, request_set
from leilao.simulation import GUARANTEED_ROUND, run_simulation

GRADE = [
    Discipline("D1", seats=6, hours=60),
    Discipline("D2", seats=6, hours=60),
    Discipline("D3", seats=4, hours=60, prerequisites=("D1",)),
    Discipline("D4", seats=4, hours=90, prerequisites=("D2",)),
    Discipline("D5", seats=3, hours=60, prerequisites=("D3",)),
]

WORKLOAD = 180
NEUTRAL = AffinityProfile("Padrão", "concentrated", 1, WORKLOAD, 100)
HOURS = {d.name: d.hours for d in GRADE}


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=6,
        entry_periods=3,
        students_per_period=3,
        rounds=2,
        affinity_profiles=[NEUTRAL],
        mechanism="ranking",
        seed=11,
    )
    return SimulationConfig(**{**base, **overrides})


# --- o pedido do aluno: mochila 0-1 sobre a carga horária, eq. (50) ---------


def test_the_request_never_exceeds_the_fraction_of_the_workload():
    """Σ w_x <= U_a · W_a^(t,r) — a eq. (50) é o teto do pedido."""
    utilities = {"D1": 0.3, "D2": 0.25, "D3": 0.2, "D4": 0.15, "D5": 0.1}
    wanted = request_set(
        utilities=utilities,
        available=list(utilities),
        hours=HOURS,
        capacity=WORKLOAD,
        spend_fraction=0.5,
    )
    assert sum(HOURS[name] for name in wanted) <= 0.5 * WORKLOAD


def test_the_request_maximises_utility_within_the_budget():
    """Com 120 h de teto cabem duas de 60 h; a mochila pega as duas de maior
    utilidade, e não a de 90 h sozinha, ainda que ela seja a preferida."""
    utilities = {"D4": 0.4, "D1": 0.35, "D2": 0.3, "D3": 0.05}
    wanted = request_set(
        utilities=utilities,
        available=list(utilities),
        hours=HOURS,
        capacity=120,
        spend_fraction=1.0,
    )
    assert sorted(wanted) == ["D1", "D2"]


def test_the_request_takes_everything_when_everything_fits():
    utilities = {"D1": 0.6, "D2": 0.4}
    wanted = request_set(
        utilities=utilities,
        available=list(utilities),
        hours=HOURS,
        capacity=WORKLOAD,
        spend_fraction=1.0,
    )
    assert sorted(wanted) == ["D1", "D2"]


def test_an_empty_or_unaffordable_set_asks_for_nothing():
    assert (
        request_set(
            utilities={"D1": 0.5},
            available=[],
            hours=HOURS,
            capacity=WORKLOAD,
            spend_fraction=1.0,
        )
        == []
    )
    # Teto de 30 h não comporta nem a disciplina mais leve.
    assert (
        request_set(
            utilities={"D1": 0.5},
            available=["D1"],
            hours=HOURS,
            capacity=60,
            spend_fraction=0.5,
        )
        == []
    )


# --- a alocação: ordem decrescente de CR -----------------------------------


def test_the_higher_grade_average_takes_the_last_seat():
    requests = [("baixo", "D5"), ("alto", "D5")]
    granted = allocate_by_ranking(
        requests=requests,
        priority={("baixo", "D5"): 6.0, ("alto", "D5"): 8.5},
        seats={"D5": 1},
    )
    assert granted == [("alto", "D5")]


def test_the_sweep_never_hands_out_more_seats_than_there_are():
    requests = [(f"a{i}", "D5") for i in range(10)]
    granted = allocate_by_ranking(
        requests=requests,
        priority={key: float(i) for i, key in enumerate(requests)},
        seats={"D5": 3},
    )
    assert len(granted) == 3
    # Os três de maior prioridade, na ordem em que foram atendidos.
    assert granted == [("a9", "D5"), ("a8", "D5"), ("a7", "D5")]


def test_the_sweep_leaves_the_seat_count_untouched():
    seats = {"D5": 2}
    allocate_by_ranking(
        requests=[("a", "D5")], priority={("a", "D5"): 7.0}, seats=seats
    )
    assert seats == {"D5": 2}


# --- a simulação inteira sob a linha de base -------------------------------


def test_the_baseline_runs_and_respects_the_seats():
    result = run_simulation(make_config())
    for period in result.periods:
        for snapshot in period.disciplines:
            assert snapshot.filled <= snapshot.seats


def test_the_baseline_respects_the_workload_cap():
    """eq. (4): a carga obtida no período nunca passa de W_a. Aqui ela é
    resolvida pelo aluno, não pelo PLI — e é justamente por isso que convém
    conferir."""
    result = run_simulation(make_config())
    hours = {d.name: d.hours for d in GRADE}
    for history in result.histories:
        for record in history.periods:
            won = [r for r in record.requests if r.won_round is not None]
            assert sum(hours[r.discipline] for r in won) <= WORKLOAD


def test_the_baseline_has_no_credits_anywhere():
    """Sem leilão não há orçamento, preço nem retorno — e as grandezas saem
    `None`, não zero: zero se leria como "ninguém gastou"."""
    result = run_simulation(make_config())
    for period in result.periods:
        assert period.aggregate.prices is None
        for snapshot in period.disciplines:
            assert snapshot.mean_price is None
        for report in [period.aggregate, *period.rounds]:
            for group in [report.overall, *report.by_cohort, *report.by_aptitude]:
                assert group.mean_credits is None
                assert group.credits_per_student is None
                assert group.credits_per_seat is None
                assert group.mean_bids is None
                assert group.mean_credit_return is None


def test_the_baseline_still_grants_the_entrants_their_first_period_seats():
    """A matrícula garantida é do modelo da universidade, não do mecanismo:
    vale igual nos dois lados."""
    result = run_simulation(make_config())
    first = result.histories[0].periods[0]
    granted = [r for r in first.requests if r.won_round == GUARANTEED_ROUND]
    assert {r.discipline for r in granted} == {"D1", "D2"}
    # E não custa nada: na linha de base o crédito não existe.
    assert all(r.paid == 0 for r in granted)


def test_the_baseline_is_deterministic():
    first = run_simulation(make_config())
    second = run_simulation(make_config())
    assert first.periods[-1].aggregate.overall == second.periods[-1].aggregate.overall


def test_the_two_mechanisms_start_from_the_same_population():
    """A condição metodológica da Seção 7.3: mesma seed, mesma inicialização.
    O que diverge depois é consequência do mecanismo, não do sorteio."""
    credits = run_simulation(make_config(mechanism="credits"))
    ranking = run_simulation(make_config(mechanism="ranking"))
    assert [s.name for s in credits.students] == [s.name for s in ranking.students]
    assert [s.entry_period for s in credits.students] == [
        s.entry_period for s in ranking.students
    ]
    assert [s.aptitude for s in credits.students] == [s.aptitude for s in ranking.students]


def test_the_two_mechanisms_allocate_differently():
    credits = run_simulation(make_config(mechanism="credits"))
    ranking = run_simulation(make_config(mechanism="ranking"))
    assert credits.periods[-1].aggregate.overall.metrics != (
        ranking.periods[-1].aggregate.overall.metrics
    )


def test_the_credit_return_policy_has_no_effect_on_the_baseline():
    """f_γ devolve parte do preço pago, e na linha de base não houve preço."""
    none = run_simulation(make_config(credit_return="none"))
    full = run_simulation(make_config(credit_return="full"))
    assert [s.graduated_at for s in none.students] == [s.graduated_at for s in full.students]
    assert none.periods[-1].aggregate.overall == full.periods[-1].aggregate.overall


# --- a comparação ----------------------------------------------------------


def test_the_comparison_pairs_the_seeds_across_every_arm():
    result = run_comparison(make_config(), runs=3)
    assert result.runs == 3
    assert [arm.key for arm in result.arms] == [arm.key for arm in ARMS]
    for arm in result.arms:
        assert [r.seed for r in arm.runs] == [1, 2, 3]


def test_the_comparison_fixes_the_credit_return_per_arm():
    """O retorno deixa de ser parâmetro do cenário e vira o eixo do
    experimento: um braço o usa proporcional, os outros dois não o usam."""
    result = run_comparison(make_config(credit_return="unit"), runs=2)

    assert [(a.mechanism, a.credit_return) for a in result.arms] == [
        ("ranking", "none"),
        ("credits", "ratio"),
        ("credits", "none"),
    ]
    # O `unit` do cenário não chegou a lugar nenhum.
    assert all(arm.credit_return != "unit" for arm in result.arms)


def test_the_two_credit_arms_differ_only_by_the_return():
    """Mesma seed, mesmo mecanismo, mesma população: o que separa os dois é só
    a política de retorno — e ela precisa separar, senão o braço é redundante."""
    result = run_comparison(make_config(), runs=4)
    with_return = next(a for a in result.arms if a.key == "credits_return")
    without = next(a for a in result.arms if a.key == "credits")

    assert [r.seed for r in with_return.runs] == [r.seed for r in without.runs]
    assert [r.efficiency for r in with_return.runs] != [
        r.efficiency for r in without.runs
    ]


def test_the_comparison_ignores_the_scenario_seed():
    """Numa comparação a seed deixa de ser parâmetro e vira o eixo da amostra."""
    first = run_comparison(make_config(seed=1), runs=2)
    second = run_comparison(make_config(seed=999), runs=2)
    assert first == second


def test_the_comparison_rejects_a_run_count_out_of_range():
    with pytest.raises(ValueError):
        run_comparison(make_config(), runs=0)


def test_the_summary_weights_the_periods_by_the_active_students():
    """A média ponderada tem de cair entre o menor e o maior valor por período
    — e, com a drenagem, ficar mais perto dos períodos cheios."""
    result = run_simulation(make_config())
    summary = summarize(result, seed=7)
    efficiencies = [
        p.aggregate.overall.metrics.efficiency
        for p in result.periods
        if p.aggregate.overall.metrics
    ]
    assert min(efficiencies) <= summary.efficiency <= max(efficiencies)
    assert summary.periods == len(result.periods)


def test_the_saturation_has_one_figure_per_round_and_decays():
    """Uma posição por rodada, e o que foi ganho *naquela* rodada — não o
    acumulado. Daí a série cair: a primeira pega o que estava livre, as
    seguintes o que sobrou."""
    config = make_config(rounds=3)
    series = allocations_per_round(run_simulation(config))

    assert len(series) == 3
    assert all(value is not None for value in series)
    assert series[0] >= series[1] >= series[2]


def test_the_saturation_sums_to_the_allocation_of_the_period():
    """Somadas, as rodadas dão as vagas por aluno do período — é a mesma
    grandeza fatiada, não uma contagem à parte."""
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
    """A linha de base também tem rodadas: o aluno refaz a mochila com a carga
    horária que lhe sobrou, então ali a saturação também se mede."""
    for mechanism in ("credits", "ranking"):
        series = allocations_per_round(
            run_simulation(make_config(mechanism=mechanism, rounds=2))
        )
        assert len(series) == 2
        assert series[0] > 0


def test_the_summary_survives_a_simulation_with_no_active_students():
    """Guarda: sem período publicado não há média a tirar, e o resumo sai zerado
    em vez de dividir por zero."""
    empty = dataclasses.replace(run_simulation(make_config()), periods=[])
    assert summarize(empty, seed=1).efficiency == 0.0
