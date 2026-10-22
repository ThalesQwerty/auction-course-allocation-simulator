"""A linha de base por CR (Seção 7.3.1, eqs. 49-50) e a comparação entre os
dois mecanismos (Seção 7.3)."""
import dataclasses

import pytest

from leilao.behavior import DISTRIBUTION_BINS
from leilao.grading import DISTRIBUTION_BINS as GRADE_BINS
from leilao.comparison import (
    ARMS,
    MAX_RUNS,
    allocations_per_round,
    run_comparison,
    run_sweep,
    summarize,
)
from disciplines import disciplines_from_predecessors
from leilao.config import Discipline, SimulationConfig
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
        entry_periods=3,
        students_per_period=3,
        rounds=2,
        max_hours=WORKLOAD,
        mechanism="ranking",
        seed=11,
    )
    return SimulationConfig(**{**base, **overrides})


# --- o pedido do aluno: mochila 0-1 sobre a carga horária, eq. (50) ---------


def test_the_request_is_everything_eligible_in_preference_order():
    """A mochila 0-1 saiu: o aluno pede tudo que lhe é elegível, da que mais
    quer para a que menos quer, e a carga horária é resolvida na concessão.
    Sem isso o eixo ordenação × PLI não existe do lado do CR — o pedido já
    caberia em W_a por construção e os dois resolvedores empatariam sempre."""
    utilities = {"D1": 0.3, "D2": 0.25, "D3": 0.2, "D4": 0.15, "D5": 0.1}
    wanted = request_set(utilities=utilities, available=list(utilities))
    assert wanted == ["D1", "D2", "D3", "D4", "D5"]
    # E ele pede muito mais do que cabe: é esse excesso que dá o que decidir
    # ao alocador.
    assert sum(HOURS[name] for name in wanted) > WORKLOAD


def test_the_request_covers_only_what_is_available_and_wanted():
    utilities = {"D1": 0.6, "D2": 0.0, "D3": 0.4}
    assert request_set(utilities=utilities, available=["D1", "D3"]) == ["D1", "D3"]
    # Utilidade zero é o que marca o inelegível, e não entra no pedido.
    assert request_set(utilities=utilities, available=list(utilities)) == ["D1", "D3"]
    assert request_set(utilities={"D1": 0.5}, available=[]) == []


def test_a_tie_in_the_request_goes_to_the_discipline_listed_first():
    """Empate sai na ordem da grade, a mesma que desempata o lance — e não na
    ordem alfabética nem na de `available`."""
    tied = {"D2": 0.25, "D1": 0.25, "D5": 0.25, "D3": 0.25}
    assert request_set(utilities=tied, available=list(tied)) == ["D2", "D1", "D5", "D3"]
    shuffled = request_set(utilities=tied, available=["D5", "D3", "D1", "D2"])
    assert shuffled == ["D2", "D1", "D5", "D3"]


# --- a alocação: ditadura serial por CR, carga resolvida ex-post -----------


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
    """Ditadura serial: o aluno entra na ordem do CR e leva o que quer, na
    própria ordem. Com 120 h de teto e três pedidos de 60 h, ele fica com os
    dois primeiros da *lista dele* — não com os que calharem."""
    granted = allocate_by_ranking(
        requests=[("a", "D1"), ("a", "D2"), ("a", "D3")],
        priority={"a": 7.0},
        seats={"D1": 5, "D2": 5, "D3": 5},
        hours=HOURS,
        capacity={"a": 120},
    )
    assert granted == [("a", "D1"), ("a", "D2")]


def test_the_sweep_never_hands_out_more_seats_than_there_are():
    requests = [(f"a{i}", "D5") for i in range(10)]
    granted = allocate_by_ranking(
        requests=requests,
        priority={f"a{i}": float(i) for i in range(10)},
        seats={"D5": 3},
        hours=HOURS,
        capacity={f"a{i}": WORKLOAD for i in range(10)},
    )
    assert len(granted) == 3
    assert granted == [("a9", "D5"), ("a8", "D5"), ("a7", "D5")]


def test_the_sweep_leaves_the_seat_count_untouched():
    seats = {"D5": 2}
    capacity = {"a": WORKLOAD}
    allocate_by_ranking(
        requests=[("a", "D5")],
        priority={"a": 7.0},
        seats=seats,
        hours=HOURS,
        capacity=capacity,
    )
    assert seats == {"D5": 2}
    assert capacity == {"a": WORKLOAD}


def test_the_two_resolvers_agree_when_the_workload_is_slack():
    """Sem a carga apertando, o problema se separa por disciplina e o guloso é
    ótimo — então as duas células da linha do CR coincidem. É a razão de o eixo
    só ter conteúdo em cenário com elegível maior que W_a."""
    requests = [("a", "D1"), ("a", "D2"), ("b", "D1"), ("b", "D2")]
    kwargs = dict(
        requests=requests,
        priority={"a": 8.0, "b": 6.0},
        seats={"D1": 1, "D2": 2},
        hours=HOURS,
        capacity={"a": WORKLOAD, "b": WORKLOAD},
    )
    assert sorted(allocate_by_ranking(**kwargs)) == sorted(allocate_by_ilp(**kwargs))


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
            for group in [report.overall, *report.by_cohort]:
                assert group.mean_credits is None
                assert group.credits_per_student is None
                assert group.credits_per_seat is None
                assert group.mean_bids is None
                assert group.mean_credit_return is None


def test_the_baseline_still_grants_the_entrants_their_entry_seats():
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
    # O perfil era a terceira coisa conferida aqui; sem perfis, o que resta da
    # inicialização comum são o nome e o t_a. A matriz de notas também é a
    # mesma, mas só se observa pelo CR, que diverge assim que a alocação
    # diverge — então não dá para afirmá-la daqui.


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
    a política de retorno — e ela precisa separar, senão o braço é redundante.

    Precisa de um cenário **apertado** para a prova fazer sentido: o retorno só
    muda alguma coisa onde o crédito é escasso. Com os 3 alunos por período do
    `make_config` ninguém disputa nada, todo preço fica no piso e os dois braços
    saem idênticos — o que não diz que o retorno é inócuo, diz que ali não havia
    o que devolver. Cinco alunos por período bastam para a disputa existir.
    """
    result = run_comparison(make_config(students_per_period=5), runs=4)
    with_return = next(a for a in result.arms if a.key == "credits_return")
    without = next(a for a in result.arms if a.key == "credits")

    assert [r.seed for r in with_return.runs] == [r.seed for r in without.runs]
    assert [r.efficiency for r in with_return.runs] != [
        r.efficiency for r in without.runs
    ]


# --- a varredura da forma da preferência ------------------------------------


def test_the_sweep_walks_a_linear_range_of_sigma():
    """Passos iguais do mínimo ao máximo, e o sigma do cenário vem junto como
    `canonical` — ele é o que o boxplot mede, e **não** precisa cair exatamente
    num ponto varrido."""
    sweep = run_sweep(
        make_config(mechanism="credits", utility_sigma=0.8),
        min_sigma=0.5,
        max_sigma=2.5,
        points=5,
        runs=2,
    )
    assert sweep.canonical == 0.8
    assert [round(p.sigma, 6) for p in sweep.points] == [0.5, 1.0, 1.5, 2.0, 2.5]
    for point in sweep.points:
        assert [a.key for a in point.arms] == [a.key for a in ARMS]
        seeds = [[r.seed for r in arm.runs] for arm in point.arms]
        assert seeds[0] == seeds[1] == seeds[2] == [1, 2]
        # O histograma da causa vem com o ponto.
        assert len(point.distribution) == DISTRIBUTION_BINS
        assert sum(point.distribution) == pytest.approx(1.0)


def test_each_sweep_point_really_runs_at_its_own_sigma():
    """Se o sigma não chegasse à simulação, todos os pontos sairiam iguais — é o
    jeito mais direto de provar que a varredura varre."""
    sweep = run_sweep(
        make_config(mechanism="credits", students_per_period=5),
        min_sigma=0.5,
        max_sigma=3.0,
        points=4,
        runs=2,
    )
    psi = [
        tuple(r.efficiency for arm in point.arms if arm.key == "credits" for r in arm.runs)
        for point in sweep.points
    ]
    assert len(set(psi)) == len(psi), "pontos diferentes deveriam medir coisas diferentes"
    # E o histograma acompanha: mais concentração, mais massa na primeira faixa.
    assert sweep.points[0].distribution[0] < sweep.points[-1].distribution[0]


def test_an_invalid_sweep_range_is_rejected():
    with pytest.raises(ValueError, match="não pode passar do máximo"):
        run_sweep(make_config(), min_sigma=3.0, max_sigma=0.5, points=4, runs=1)
    with pytest.raises(ValueError, match="deve ser > 0"):
        run_sweep(make_config(), min_sigma=0.0, max_sigma=2.0, points=4, runs=1)
    with pytest.raises(ValueError, match="pelo menos 2 pontos"):
        run_sweep(make_config(), min_sigma=0.5, max_sigma=2.0, points=1, runs=1)
    with pytest.raises(ValueError, match="acima do limite"):
        run_sweep(make_config(), min_sigma=0.5, max_sigma=2.0, points=99, runs=1)


def test_a_sweep_that_would_cost_too_much_is_rejected():
    """O teto é de simulações, não de pontos: uma faixa pequena com muitas
    execuções custa tanto quanto uma faixa grande com poucas."""
    with pytest.raises(ValueError, match="acima do limite de"):
        run_sweep(make_config(), min_sigma=0.5, max_sigma=3.0, points=20, runs=MAX_RUNS)


def test_the_comparison_ignores_the_scenario_seed():
    """Numa comparação a seed deixa de ser parâmetro e vira o eixo da amostra.

    Vale para o resultado **inteiro**, histogramas inclusive: eles são sorteados
    à parte das execuções, e sortear com a seed do cenário faria dois cenários
    idênticos a menos dela devolverem respostas diferentes — exatamente o que
    esta propriedade promete que não acontece.
    """
    first = run_comparison(make_config(seed=1), runs=2)
    second = run_comparison(make_config(seed=999), runs=2)
    assert first == second
    assert first.utility_distribution and first.grade_distribution


def test_the_comparison_carries_both_scenario_distributions():
    """Os dois histogramas de entrada vêm com a comparação, para a tela mostrar
    de onde vieram os números. Somam 1, e as notas têm uma faixa a mais que as
    utilidades porque a escala delas é [0, 10]."""
    result = run_comparison(make_config(), runs=2)
    assert len(result.utility_distribution) == DISTRIBUTION_BINS
    assert len(result.grade_distribution) == GRADE_BINS
    assert sum(result.utility_distribution) == pytest.approx(1.0)
    assert sum(result.grade_distribution) == pytest.approx(1.0)

    # A das notas não depende de sigma; a das utilidades sim.
    wider = run_comparison(make_config(utility_sigma=3.0), runs=2)
    assert wider.grade_distribution == result.grade_distribution
    assert wider.utility_distribution != result.utility_distribution


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
