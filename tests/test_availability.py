"""Disponibilidade, exclusão e os dois eixos de perfil."""
from __future__ import annotations

import math

import numpy as np
import pytest

from profiles import always_available
from disciplines import disciplines_from_predecessors

from leilao.availability import draw_availability
from leilao.config import (
    Discipline,
    DEFAULT_AVAILABILITY,
    AvailabilityShape,
    SimulationConfig,
)
from leilao.equations import (
    RequestStates,
    effective_load,
    exclusion_rate,
    request_funnel,
    request_states,
    retained_set,
)
from leilao.grading import GradeMeans, draw_grade_quantiles, grade_for_attempt
from leilao.population import Student, generate_students
from leilao.simulation.snapshots import Axis
from leilao.equations import value_band, value_band_names
from collections import Counter
from leilao.simulation import run_simulation

GRADE = disciplines_from_predecessors(
    ("D1", 160, 60),
    ("D2", 160, 60),
    ("D3", 96, 90, ("D1",)),
    ("D4", 96, 90, ("D2",)),
)


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=6,
        max_residence=4,
        students_per_entry_class=18,
        selectivity_median=2.0,
        rounds=2,
        max_hours=240,
        seed=7,
    )
    return SimulationConfig(**{**base, **overrides})


def test_the_effective_load_rounds_to_the_nearest_hour():
    """A disponibilidade já vem em horas: a carga efetiva só arredonda."""
    assert effective_load(availability=360.0) == 360
    assert effective_load(availability=180.4) == 180
    assert effective_load(availability=0.0) == 0
    assert effective_load(availability=319.5) == 320


def test_the_effective_load_has_no_ceiling():
    """O teto de carga é do **sistema**, não do aluno, e por isso a carga"""
    assert effective_load(availability=500.0) == 500


def test_the_effective_load_rejects_a_negative_availability():
    with pytest.raises(ValueError):
        effective_load(availability=-1.0)


def test_the_knapsack_beats_dropping_by_ascending_utility():
    """O contraexemplo que justifica a mochila: a heurística sacrifica duas"""
    utilities = {"Algoritmos": 0.22, "Cálculo": 0.13, "Física": 0.11}
    hours = {"Algoritmos": 90, "Cálculo": 60, "Física": 60}

    kept = retained_set(
        utilities=utilities, hours=hours, obtained=utilities, load=122
    )
    assert kept == ["Cálculo", "Física"]
    assert sum(utilities[n] for n in kept) == pytest.approx(0.24)
    assert sum(hours[n] for n in kept) <= 122


def test_the_knapsack_keeps_everything_when_the_load_fits():
    utilities = {"A": 0.3, "B": 0.2}
    hours = {"A": 60, "B": 60}
    assert retained_set(
        utilities=utilities, hours=hours, obtained=utilities, load=240
    ) == ["A", "B"]


def test_the_knapsack_breaks_ties_toward_the_discipline_listed_first():
    """Mesma regra do resto do motor: utilidades empatadas resolvem pela ordem"""
    utilities = {"primeira": 0.2, "segunda": 0.2}
    hours = {"primeira": 60, "segunda": 60}
    assert retained_set(
        utilities=utilities, hours=hours, obtained=utilities, load=60
    ) == ["primeira"]
    assert retained_set(
        utilities={"segunda": 0.2, "primeira": 0.2},
        hours=hours,
        obtained=utilities,
        load=60,
    ) == ["segunda"]


def test_the_knapsack_returns_nothing_when_the_load_is_zero():
    utilities = {"A": 0.3}
    assert retained_set(
        utilities=utilities, hours={"A": 60}, obtained=utilities, load=0
    ) == []


def test_excluding_returns_no_credit_at_all():
    """A excluída não devolve crédito nenhum: o aluno perde o que investiu para"""
    result = run_simulation(make_config())
    excluidas = [
        record
        for history in result.histories
        for period in history.periods
        for record in period.requests
        if record.excluded
    ]
    assert excluidas, "o cenário deveria ter exclusões"
    assert all(record.returned == 0 for record in excluidas)
    assert any(record.paid > 0 for record in excluidas)


def test_the_exclusion_rate_is_zero_when_nothing_was_allocated():
    """Recorte sem vaga obtida não desperdiçou nada — o que é diferente de"""
    assert exclusion_rate(excluded=0, allocated=0) == 0.0
    assert exclusion_rate(excluded=3, allocated=12) == 0.25
    with pytest.raises(ValueError):
        exclusion_rate(excluded=4, allocated=3)


def test_the_six_states_partition_what_is_still_missing():
    """Cada disciplina que ainda falta cai em exatamente um estado, e a soma é"""
    states = request_states(
        catalogue=["A", "B", "C", "D", "E", "F"],
        approved={"A", "D"},
        eligible=["B", "C", "D"],
        requested={"B", "D"},
        won={"B", "D"},
        retained={"D"},
    )
    assert states == RequestStates(
        not_eligible=2,
        not_requested=1,
        refused=0,
        excluded=1,
        failed=0,
        approved=1,
    )
    assert states.total == 5


def test_the_already_approved_leave_the_denominator():
    """É o que impede "não elegível" de crescer por progresso e encolher por"""
    antes = request_states(
        catalogue=["A", "B"],
        approved=set(),
        eligible=["A", "B"],
        requested={"A"},
        won={"A"},
        retained={"A"},
    )
    depois = request_states(
        catalogue=["A", "B"],
        approved={"A"},
        eligible=["B"],
        requested=set(),
        won=set(),
        retained=set(),
    )
    assert antes.total == 2
    assert depois.total == 1
    assert depois.not_eligible == 0


def test_the_average_is_per_student_and_never_a_sum():
    rows = [
        RequestStates(4, 2, 0, 1, 0, 1),
        RequestStates(2, 2, 0, 1, 2, 1),
    ]
    assert RequestStates.average(rows) == RequestStates(3, 2, 0, 1, 1, 1)
    assert RequestStates.average([]) == RequestStates(0, 0, 0, 0, 0, 0)


def test_each_funnel_share_divides_by_the_node_before_it():
    """Cada fração responde por um nó, e o denominador é o que chegou até"""
    states = RequestStates(
        not_eligible=4,
        not_requested=3,
        refused=2,
        excluded=1,
        failed=2,
        approved=3,
    )
    funnel = request_funnel(states)

    assert states.total == 15
    assert funnel.requested_share == pytest.approx(8 / 15)
    assert funnel.granted_share == pytest.approx(6 / 8)
    assert funnel.attended_share == pytest.approx(5 / 6)
    assert funnel.approved_share == pytest.approx(3 / 5)


def test_an_empty_node_gives_none_and_never_zero():
    """"Ninguém pediu nada" é diferente de "ninguém foi deferido" — e zero"""
    nothing = request_funnel(RequestStates(5, 5, 0, 0, 0, 0))
    assert nothing.requested_share == 0.0
    assert nothing.granted_share is None
    assert nothing.attended_share is None
    assert nothing.approved_share is None
    assert request_funnel(RequestStates(0, 0, 0, 0, 0, 0)).requested_share is None


def test_the_attended_share_is_the_complement_of_the_exclusion_rate():
    """A redundância é exata, e é bom que esteja declarada: a fração de"""
    states = RequestStates(2, 2, 1, 3, 4, 5)
    funnel = request_funnel(states)
    allocated = int(states.excluded + states.failed + states.approved)
    assert funnel.attended_share == pytest.approx(
        1 - exclusion_rate(excluded=int(states.excluded), allocated=allocated)
    )


def test_the_cohort_is_typed_not_derived():
    """O tamanho da coorte é digitado. Era derivado do produto das combinações"""
    config = make_config(students_per_entry_class=20)
    students = generate_students(config, np.random.default_rng(0))
    assert config.students_per_period == 20
    assert len([s for s in students if s.entry_period == 1]) == 20


def test_the_cut_belongs_to_the_band_it_opens():
    """Com cortes 5 e 7, um CR exatamente 7 está em "7–10" — a comparação é"""
    cuts = (5.0, 7.0)
    assert value_band(value=4.9, cuts=cuts) == 0
    assert value_band(value=5.0, cuts=cuts) == 1
    assert value_band(value=6.9, cuts=cuts) == 1
    assert value_band(value=7.0, cuts=cuts) == 2
    assert value_band_names(cuts=cuts, low=0.0, high=10.0) == ["0–5", "5–7", "7–10"]


def test_one_band_is_the_whole_university():
    config = make_config(grade_cuts=(), reserve_cuts=())
    axis = Axis.states(config)["reserve"]
    assert axis.order == ["Geral"]


def test_the_marginal_of_the_quantile_stays_uniform():
    """O nível basilar reparte a variância, não a muda: a calibragem da nota"""
    config = make_config(students_per_entry_class=150)
    students = generate_students(config, np.random.default_rng(0))
    valores = list(
        draw_grade_quantiles(students, GRADE, config, np.random.default_rng(1)).values()
    )
    assert np.mean(valores) == pytest.approx(0.5, abs=0.02)
    assert np.std(valores) == pytest.approx(1 / np.sqrt(12), abs=0.02)


def test_a_student_built_by_hand_sits_at_the_median():
    """Quem constrói um aluno à mão não está escolhendo uma ponta."""
    student = Student(id="x", name="X", credits=10)
    assert student.availability_anchor == 0.5
    assert student.selectivity_anchor == 0.5


def test_availability_is_drawn_once_per_student_and_period():
    """Ao contrário do desempenho, que é um só para o curso inteiro: o tempo"""
    config = make_config()
    students = generate_students(config, np.random.default_rng(0))
    drawn = draw_availability(students, config, np.random.default_rng(0))

    assert len(drawn) == len(students) * config.periods
    assert all(value > 0.0 for value in drawn.values())
    assert any(value > config.max_hours for value in drawn.values())
    reduced = min(students, key=lambda s: s.availability_anchor)
    row = [drawn[(reduced.id, t)] for t in range(1, config.periods + 1)]
    assert len(set(row)) == len(row)


def test_tripling_the_seats_moves_no_availability_draw():
    """A mesma invariante que o interesse tem: nada é sorteado"""
    import dataclasses

    config = make_config()
    bigger = dataclasses.replace(
        config,
        disciplines=[dataclasses.replace(d, seats=d.seats * 3) for d in GRADE],
    )
    students = generate_students(config, np.random.default_rng(0))
    assert draw_availability(students, config, np.random.default_rng(0)) == (
        draw_availability(students, bigger, np.random.default_rng(0))
    )


def test_excluding_costs_no_attempt_and_leaves_the_record_without_a_grade():
    """Quem exclui e refaz no semestre seguinte volta como primeira"""
    result = run_simulation(make_config())
    excluded = [
        request
        for history in result.histories
        for record in history.periods
        for request in record.requests
        if request.excluded
    ]
    assert excluded, "o cenário deveria produzir exclusões"
    for request in excluded:
        assert request.won_round is not None
        assert request.attempt is None
        assert request.grade is None
        assert not request.approved


def test_the_retained_load_fits_the_availability_of_the_period():
    result = run_simulation(make_config())
    for history in result.histories:
        for record in history.periods:
            assert record.retained_hours <= record.effective_load
            assert record.retained_hours <= record.enrolled_hours


def test_the_excluded_seat_does_not_return_to_the_offer():
    """Exclui-se depois de encerradas as alocações do período, então a vaga"""
    result = run_simulation(make_config())
    for period in result.periods:
        for snapshot in period.disciplines:
            assert snapshot.exclusions <= snapshot.filled
            assert snapshot.filled <= snapshot.seats


def test_a_full_availability_scenario_never_excludes():
    """Com disponibilidade praticamente cheia a mecânica some, e o modelo"""
    result = run_simulation(
        make_config(availability=always_available(240))
    )
    for history in result.histories:
        for record in history.periods:
            assert record.retained_hours == record.enrolled_hours
            assert not any(r.excluded for r in record.requests)
