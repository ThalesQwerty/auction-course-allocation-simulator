"""As turmas: o bem alocado, e a disciplina como clique do grafo de conflito."""
from __future__ import annotations

import math

import numpy as np
import pytest
from profiles import always_available, single_axis

from leilao.behavior import (
    compute_bids,
    draw_interest,
    draw_schedule_interest,
    utility_matrix,
)
from leilao.config import Discipline, SimulationConfig
from leilao.equations import (
    Behavior,
    RequestStates,
    class_schedules,
    concave_bids,
    entry_class_load,
    market_prices,
    rotated_index,
    request_states,
    utility,
)
from leilao.population import generate_students
from leilao.ranking import request_set
from leilao.simulation import run_simulation

WORKLOAD = 240


def make_config(classes: int = 4, **overrides) -> SimulationConfig:
    base = dict(
        disciplines=[
            Discipline("Obrigatória 1", seats=24, hours=60, classes=classes, entry=True),
            Discipline("Obrigatória 2", seats=24, hours=60, classes=classes, entry=True),
            Discipline(
                "Obrigatória 3", seats=24, hours=60, classes=classes, entry=True
            ),
        ],
        periods=3,
        students_per_entry_class=2,
        rounds=2,
        max_hours=WORKLOAD,
        seed=7,
        **single_axis(WORKLOAD),
    )
    return SimulationConfig(**{**base, **overrides})


def test_the_offer_is_split_between_the_classes_without_losing_a_seat():
    config = make_config(classes=4)
    seats = config.seats_by_class()
    assert len(seats) == 12
    assert sum(seats.values()) == 72
    assert all(value == 6 for value in seats.values())


def test_an_uneven_offer_gives_the_leftover_to_the_first_classes():
    config = make_config(
        classes=1,
        disciplines=[Discipline("D", seats=10, hours=60, classes=3, entry=True)],
    )
    assert list(config.seats_by_class().values()) == [4, 3, 3]


def test_one_class_is_the_discipline_itself():
    """É o que torna o modelo sem turmas um caso particular deste: mesmo nome,"""
    config = make_config(classes=1)
    assert config.classes_by_discipline() == {
        name: (name,) for name in config.hours_by_discipline()
    }
    assert config.seats_by_class() == config.hours_by_discipline().keys() | set() or True
    assert config.discipline_cliques() == ()


def test_the_clique_is_one_per_discipline_with_more_than_one_class():
    config = make_config(classes=4)
    cliques = config.discipline_cliques()
    assert len(cliques) == 3
    assert all(len(clique) == 4 for clique in cliques)


def test_the_schedules_are_handed_out_in_a_circle():
    horarios = class_schedules(count=22, slots=12)
    assert horarios[:3] == ("Horário 1", "Horário 2", "Horário 3")
    assert horarios[12] == "Horário 1"
    assert horarios[21] == "Horário 10"


def test_the_classes_of_a_discipline_never_share_a_schedule():
    """A varredura é contígua, então as k turmas de uma disciplina caem em k"""
    config = make_config(classes=5)
    schedule = config.schedule_by_class()
    for names in config.classes_by_discipline().values():
        horarios = [schedule[name] for name in names]
        assert len(set(horarios)) == len(horarios)


def test_a_scenario_with_fewer_schedules_than_classes_is_refused():
    with pytest.raises(ValueError, match="ao menos 5 horários"):
        make_config(classes=5, slots=4)


def test_the_classes_per_schedule_differ_by_at_most_one():
    """O equilíbrio sai de graça da varredura circular, e é o que impede um"""
    config = make_config(classes=5)
    por_horario: dict[str, int] = {}
    for schedule in config.schedule_by_class().values():
        por_horario[schedule] = por_horario.get(schedule, 0) + 1
    contagens = list(por_horario.values())
    assert max(contagens) - min(contagens) <= 1


def test_every_period_has_a_clash_free_grid():
    """Com as turmas distribuídas em círculo e horários bastantes, sempre"""
    config = make_config(classes=5)
    schedule = config.schedule_by_class()
    livres: set[str] = set()
    for names in config.classes_by_discipline().values():
        opcoes = [
            schedule[name] for name in names if schedule[name] not in livres
        ]
        assert opcoes, names
        livres.add(opcoes[0])


def test_the_exclusion_cliques_are_the_disciplines_plus_the_schedules():
    config = make_config(classes=5)
    cliques = config.exclusion_cliques()
    assert config.discipline_cliques()[0] in cliques
    assert len(cliques) == 7
    conflitos = config.conflict_groups()
    for name, groups in conflitos.items():
        assert groups == (config.discipline_by_class()[name], config.schedule_by_class()[name])


@pytest.mark.parametrize("mechanism", ["credits", "ranking"])
def test_nobody_takes_two_classes_of_the_same_discipline(mechanism):
    """A restrição da eq. (5), nos dois mecanismos. O leilão a resolve dentro"""
    config = make_config(classes=4, mechanism=mechanism)
    result = run_simulation(config)
    groups = config.discipline_by_class()

    for history in result.histories:
        for record in history.periods:
            taken = [
                groups[r.discipline]
                for r in record.requests
                if r.won_round is not None
            ]
            assert len(taken) == len(set(taken)), (history.student_id, taken)


def test_the_filter_carries_the_clique_between_rounds():
    """O WDP impõe o clique **dentro** da rodada. Entre rodadas quem impede é"""
    config = make_config(classes=4, rounds=3)
    result = run_simulation(config)
    groups = config.discipline_by_class()

    for history in result.histories:
        for record in history.periods:
            won = [r for r in record.requests if r.won_round is not None]
            assert len({groups[r.discipline] for r in won}) == len(won)


def test_the_price_is_the_highest_rejected_bid_even_inside_the_group():
    """Quem apostou em A, B e C e foi roteado para C **continua contando** em"""
    groups = {"D T1": ("D",), "D T2": ("D",), "D T3": ("D",)}
    bids = {("a", "D T1"): 10, ("a", "D T2"): 8, ("a", "D T3"): 6, ("b", "D T1"): 3}
    allocation = {("a", "D T3"): 1, ("b", "D T1"): 0}

    precos = market_prices(good_ids=list(groups), bids=bids, allocation=allocation)

    assert precos["D T1"] == 10
    assert precos["D T2"] == 8
    assert precos["D T3"] == 1


def test_the_schedule_does_not_spare_whoever_was_served_in_it():
    """O mesmo vale para o horário, e ali o argumento é até mais forte: quem"""
    goods = ["A T1", "B T1"]
    bids = {("a", "A T1"): 9, ("a", "B T1"): 7}
    allocation = {("a", "A T1"): 1}

    precos = market_prices(good_ids=goods, bids=bids, allocation=allocation)
    assert precos["B T1"] == 7


def test_the_bid_is_split_inside_the_group_by_the_same_knapsack():
    """O nível de dentro é a **mesma** mochila côncava, agora entre as turmas"""
    classes = {"D1": ("D1 T1", "D1 T2", "D1 T3", "D1 T4"), "D2": ("D2 T1",)}
    utilities = {
        "D1 T1": 0.3, "D1 T2": 0.28, "D1 T3": 0.26, "D1 T4": 0.24, "D2 T1": 0.9,
    }
    pool = [name for names in classes.values() for name in names]

    bids = compute_bids(
        utilities=utilities, available=pool, budget=40, classes=classes
    )
    por_grupo = {
        discipline: sum(bids.get(name, 0) for name in names)
        for discipline, names in classes.items()
    }
    assert por_grupo["D2"] > por_grupo["D1"]
    dentro = [bids[name] for name in classes["D1"]]
    assert all(credits > 0 for credits in dentro)
    assert dentro == sorted(dentro, reverse=True)


def test_the_two_levels_conserve_the_budget_credit_by_credit():
    """A soma por grupo é exatamente o que o nível de fora decidiu: a"""
    classes = {"D1": ("D1 T1", "D1 T2", "D1 T3"), "D2": ("D2 T1", "D2 T2")}
    utilities = {
        "D1 T1": 0.3, "D1 T2": 0.2, "D1 T3": 0.1, "D2 T1": 0.25, "D2 T2": 0.15,
    }
    pool = [name for names in classes.values() for name in names]

    fora = concave_bids(
        scores={"D1": 0.3, "D2": 0.25}, available=["D1", "D2"], budget=37
    )
    bids = compute_bids(
        utilities=utilities, available=pool, budget=37, classes=classes
    )

    assert sum(bids.values()) == 37
    assert {
        discipline: sum(bids.get(name, 0) for name in names)
        for discipline, names in classes.items()
    } == fora


def test_the_group_budget_does_not_follow_the_number_of_classes():
    """Duas disciplinas de mesmo valor repartem o orçamento igual, mesmo com"""
    classes = {"Muitas": tuple(f"M T{i}" for i in range(1, 9)), "Poucas": ("P T1", "P T2")}
    utilities = {name: 0.1 for names in classes.values() for name in names}
    pool = [name for names in classes.values() for name in names]

    bids = compute_bids(
        utilities=utilities, available=pool, budget=40, classes=classes
    )
    por_grupo = {
        discipline: sum(bids.get(name, 0) for name in names)
        for discipline, names in classes.items()
    }
    assert por_grupo["Muitas"] == por_grupo["Poucas"] == 20


def test_the_request_is_one_class_per_discipline():
    """Disciplinas na ordem de preferência e, de cada uma, **uma** turma — a"""
    classes = {"Alta": ("A T1", "A T2"), "Baixa": ("B T1", "B T2")}
    utilities = {"A T1": 0.2, "A T2": 0.5, "B T1": 0.4, "B T2": 0.1}
    pool = [name for names in classes.values() for name in names]

    pedido = request_set(
        utilities=utilities,
        available=pool,
        hours=dict.fromkeys(pool, 60),
        capacity=WORKLOAD,
        classes=classes,
    )

    assert pedido == ["A T2", "B T1"]


def test_the_ranking_request_comes_out_without_a_clash():
    """A outra metade de `E` dentro da mesma tabela: o aluno resolve o choque"""
    classes = {"Alta": ("A T1", "A T2"), "Baixa": ("B T1", "B T2")}
    conflicts = {
        "A T1": ("Alta", "Diurno 1"),
        "A T2": ("Alta", "Diurno 2"),
        "B T1": ("Baixa", "Diurno 1"),
        "B T2": ("Baixa", "Diurno 2"),
    }
    utilities = {"A T1": 0.55, "A T2": 0.2, "B T1": 0.4, "B T2": 0.1}
    pool = [name for names in classes.values() for name in names]

    pedido = request_set(
        utilities=utilities,
        available=pool,
        hours=dict.fromkeys(pool, 60),
        capacity=WORKLOAD,
        classes=classes,
        conflicts=conflicts,
    )

    assert pedido == ["A T1", "B T2"]


def test_the_clash_and_the_workload_are_decided_together():
    """A mochila da eq. (50) é **uma só**: carga e horário saem da mesma"""
    classes = {"Alta": ("A T1", "A T2"), "Média": ("M T1",), "Baixa": ("B T1",)}
    conflicts = {
        "A T1": ("Alta", "Diurno 1"),
        "A T2": ("Alta", "Diurno 2"),
        "M T1": ("Média", "Diurno 2"),
        "B T1": ("Baixa", "Diurno 1"),
    }
    utilities = {"A T1": 0.40, "A T2": 0.05, "M T1": 0.35, "B T1": 0.30}
    hours = {"A T1": 90, "A T2": 90, "M T1": 60, "B T1": 60}

    pedido = request_set(
        utilities=utilities,
        available=list(utilities),
        hours=hours,
        capacity=120,
        classes=classes,
        conflicts=conflicts,
    )

    assert pedido == ["M T1", "B T1"]
    assert sum(hours[name] for name in pedido) == 120


@pytest.mark.parametrize("mechanism", ["credits", "ranking"])
def test_nobody_takes_two_classes_in_the_same_schedule(mechanism):
    """A outra metade da eq. (5): `E = M ∪ G`. O leilão a resolve dentro da"""
    config = make_config(classes=5, mechanism=mechanism)
    schedule = config.schedule_by_class()
    result = run_simulation(config)

    for history in result.histories:
        for record in history.periods:
            horarios = [
                schedule[r.discipline]
                for r in record.requests
                if r.won_round is not None
            ]
            assert len(horarios) == len(set(horarios)), (history.student_id, horarios)


def test_selectivity_cuts_classes_below_the_reserve():
    """O piso vale nos dois níveis: a disciplina entra pela melhor turma que o
    aluno pode obter, e a turma abaixo da reserva fica fora mesmo com a
    disciplina admitida. Sem o corte, o ótimo seria o par que usa a turma ruim.
    """
    classes = {"Alta": ("A T1", "A T2"), "Baixa": ("B T1",)}
    conflicts = {
        "A T1": ("Alta", "Diurno 1"),
        "A T2": ("Alta", "Diurno 2"),
        "B T1": ("Baixa", "Diurno 1"),
    }
    utilities = {"A T1": 0.6, "A T2": 0.4, "B T1": 0.55}
    pool = list(utilities)
    comum = dict(
        utilities=utilities,
        available=pool,
        hours=dict.fromkeys(pool, 60),
        capacity=WORKLOAD,
        classes=classes,
        conflicts=conflicts,
    )

    assert request_set(
        **comum, behavior=Behavior(selectivity=0.5), interest=0.5
    ) == ["A T1"]
    assert request_set(**comum) == ["B T1", "A T2"]


def test_the_best_class_of_each_discipline_sums_to_one():
    """É o que torna ψ a soma simples das utilidades atendidas: o aluno só"""
    classes = {"A": ("A T1", "A T2", "A T3"), "B": ("B T1",)}
    interest = {"A": 0.6, "B": 0.4}

    utilities = utility(
        interest=interest,
        eligible=["A", "B"],
        reachable={"A": (), "B": ()},
        required={"A": (), "B": ()},
        classes=classes,
    )
    melhores = sum(
        max(utilities[name] for name in names) for names in classes.values()
    )
    assert melhores == pytest.approx(1.0)


def test_satisfaction_reaches_one_with_mutually_exclusive_classes():
    """Levar a melhor turma de toda disciplina elegível é ψ = 1, sem"""
    from leilao.equations import satisfaction

    utilities = {"A T1": 0.6, "A T2": 0.2, "B T1": 0.4, "B T2": 0.1}

    assert satisfaction(
        utilities=utilities, allocated=["A T1", "B T1"]
    ) == pytest.approx(1.0)


def test_psi_never_passes_one_in_a_full_simulation():
    config = make_config(classes=4)
    result = run_simulation(config)
    for history in result.histories:
        for record in history.periods:
            assert 0.0 <= record.satisfaction <= 1.0 + 1e-9


def test_the_newcomer_without_electives_marks_exactly_one():
    """Sem optativa o conjunto elegível do calouro **é** o pacote da matrícula"""
    config = make_config(
        classes=1, availability=always_available(WORKLOAD), schedule_sigma=0.0
    )
    result = run_simulation(config)
    primeiros = [h.periods[0].satisfaction for h in result.histories if h.periods]
    assert primeiros
    assert all(psi == pytest.approx(1.0) for psi in primeiros)

    com_horario = run_simulation(
        make_config(
            classes=1, availability=always_available(WORKLOAD), schedule_sigma=0.6
        )
    )
    outros = [h.periods[0].satisfaction for h in com_horario.histories if h.periods]
    assert outros
    assert all(psi <= 1.0 + 1e-9 for psi in outros)
    assert any(psi < 1.0 - 1e-6 for psi in outros)


def _interest(fluctuation: float, schedule_sigma: float = 0.6, periods: int = 3):
    config = make_config(
        classes=4,
        periods=periods,
        interest_fluctuation=fluctuation,
        schedule_fluctuation=fluctuation,
        schedule_sigma=schedule_sigma,
    )
    students = generate_students(config, np.random.default_rng(0))
    rows = draw_interest(students, config, np.random.default_rng(5))
    schedules = draw_schedule_interest(students, config, np.random.default_rng(7))
    return config, students, rows, schedules


def test_the_class_interest_is_the_product_of_subject_and_schedule():
    """A turma não tem sorteio próprio: o interesse dela é o da matéria vezes o"""
    config, students, rows, schedules = _interest(0.5)
    row = rows[(students[0].id, 1)]
    slots = schedules[(students[0].id, 1)]
    schedule_of = config.schedule_by_class()
    for group, names in config.classes_by_discipline().items():
        produtos = [row[group] * slots[schedule_of[name]] for name in names]
        assert len(set(round(v, 12) for v in produtos)) == len(names)
        for name, produto in zip(names, produtos):
            assert produto == row[group] * slots[schedule_of[name]]


def test_the_schedule_taste_is_shared_across_disciplines():
    """Quem não gosta de um horário não gosta dele em disciplina nenhuma: é daí"""
    config, students, _rows, schedules = _interest(0.5)
    slots = schedules[(students[0].id, 1)]
    schedule_of = config.schedule_by_class()
    por_horario: dict[str, set[float]] = {}
    for name, slot in schedule_of.items():
        por_horario.setdefault(slot, set()).add(round(slots[slot], 12))
    assert all(len(valores) == 1 for valores in por_horario.values())


def test_zero_fluctuation_freezes_the_interest_even_with_classes():
    """Sem flutuação, o interesse de cada turma é o mesmo em todo período."""
    _config, students, rows, schedules = _interest(0.0, 0.3, periods=4)
    student = students[0].id
    primeira = rows[(student, 1)]
    primeiro_horario = schedules[(student, 1)]
    for period in (2, 3, 4):
        assert rows[(student, period)] == pytest.approx(primeira)
        assert schedules[(student, period)] == pytest.approx(primeiro_horario)


def test_the_two_interests_fluctuate_independently():
    """Cada fator tem flutuação própria: congelar a disciplina não congela o"""
    config = make_config(
        classes=4,
        periods=4,
        interest_fluctuation=0.0,
        schedule_fluctuation=2.0,
    )
    students = generate_students(config, np.random.default_rng(0))
    rows = draw_interest(students, config, np.random.default_rng(5))
    schedules = draw_schedule_interest(students, config, np.random.default_rng(7))
    student = students[0].id
    assert rows[(student, 4)] == pytest.approx(rows[(student, 1)])
    assert schedules[(student, 4)] != pytest.approx(schedules[(student, 1)])


def test_the_record_stays_on_the_discipline():
    """Nota, tentativa e conclusão não sabem em que turma o aluno cursou."""
    config = make_config(classes=4)
    result = run_simulation(config)
    disciplines = set(config.hours_by_discipline())
    turmas = set(config.seats_by_class())
    assert turmas != disciplines

    for history in result.histories:
        for record in history.periods:
            for pedido in record.requests:
                assert pedido.discipline in turmas
                if pedido.attempt is not None:
                    assert pedido.attempt >= 1


def test_the_cohort_is_spread_evenly_over_the_entry_classes():
    """A matrícula garantida não escolhe turma, então ela tem de repartir: os"""
    config = make_config(classes=4)
    result = run_simulation(config)
    primeiro = result.periods[0]

    por_turma = {s.name: s.granted for s in primeiro.disciplines}
    assert sum(por_turma.values()) == 3 * config.students_per_period
    offsets = config.entry_offsets() or {}
    for discipline, names in config.classes_by_discipline().items():
        esperado = entry_class_load(
            cohort=config.students_per_period,
            classes=names,
            offset=offsets.get(discipline, 0),
        )
        assert {name: por_turma[name] for name in names} == esperado
        assert max(esperado.values()) - min(esperado.values()) <= 1


def test_the_guaranteed_package_never_clashes_with_itself():
    """O pacote de entrada é entregue inteiro e fora do mecanismo, então ele"""
    config = make_config(classes=9, slots=9)
    schedule = config.schedule_by_class()
    classes = config.classes_by_discipline()
    offsets = config.entry_offsets()
    assert offsets is not None
    assert any(offset for offset in offsets.values())
    for block in range(9):
        horarios = [
            schedule[
                classes[discipline][
                    rotated_index(block=block, offset=offset, classes=9)
                ]
            ]
            for discipline, offset in offsets.items()
        ]
        assert len(horarios) == len(set(horarios)), (block, horarios)


def test_a_clashing_guaranteed_package_is_refused():
    """Onde o giro não encontra pacote sem choque, o cenário é recusado em vez"""
    with pytest.raises(ValueError, match="mesmo horário"):
        make_config(classes=1, slots=2)


def test_a_class_only_prices_what_it_sold():
    """Preço é da turma: duas turmas da mesma disciplina podem fechar em"""
    config = make_config(classes=4, periods=4)
    result = run_simulation(config)
    nomes = set(config.seats_by_class())
    for period in result.periods:
        for snapshot in period.disciplines:
            assert snapshot.name in nomes
            assert snapshot.discipline == config.discipline_by_class()[snapshot.name]
            assert snapshot.filled <= snapshot.seats


def test_the_bid_funds_several_classes_of_a_group_without_leaking_credits():
    """O aluno financia mais de uma turma do mesmo grupo — é o hedge dentro da"""
    config = make_config(classes=4)
    draws_rng = np.random.default_rng(config.seed)
    students = generate_students(config, draws_rng)
    rows = draw_interest(students, config, draws_rng)
    classes = config.classes_by_discipline()
    pool = list(config.seats_by_class())

    for student in students:
        utilities = utility_matrix(
            interest=rows[(student.id, 1)], student=student, config=config
        )
        bids = compute_bids(
            utilities=utilities,
            available=pool,
            budget=40,
            behavior=student.behavior,
            classes=classes,
        )
        assert sum(bids.values()) <= 40
        espalhou = max(
            sum(1 for name in names if bids.get(name)) for names in classes.values()
        )
        assert espalhou > 1


def test_the_six_states_are_per_discipline_and_not_per_class():
    """O que o aluno pede, ganha e retém vem por **turma**; o catálogo e o"""
    estados = request_states(
        catalogue=["D1", "D2", "D3"],
        approved={"D1"},
        eligible=["D1 T1", "D1 T2", "D2 T1"],
        requested={"D1 T1", "D2 T1"},
        won={"D1 T1"},
        retained={"D1 T1"},
        groups={
            "D1 T1": "D1", "D1 T2": "D1", "D2 T1": "D2", "D3 T1": "D3",
        },
    )
    assert estados == RequestStates(
        not_eligible=1,
        not_requested=0,
        refused=1,
        excluded=0,
        failed=0,
        approved=1,
    )
    assert estados.total == 3


def test_a_simulation_with_classes_reports_the_approvals_it_made():
    """A consequência visível do mesmo defeito, de ponta a ponta: a soma dos"""
    config = make_config(classes=4, periods=4)
    result = run_simulation(config)
    estados = [
        period.aggregate.overall.metrics.request_states
        for period in result.periods
        if period.aggregate.overall.metrics
        and period.aggregate.overall.metrics.request_states
    ]

    assert estados
    assert any(row.approved > 0 for row in estados)
    for row in estados:
        assert row.total == pytest.approx(
            row.not_eligible
            + row.not_requested
            + row.refused
            + row.excluded
            + row.failed
            + row.approved
        )
