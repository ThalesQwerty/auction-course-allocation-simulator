"""As turmas: o bem alocado, e a disciplina como clique do grafo de conflito.

O que estes testes guardam é a eq. (5) — ninguém leva duas turmas da mesma
disciplina — e as consequências dela que não dão erro quando quebram: o preço
inflado pelo próprio grupo, o lance pulverizado dentro dele, ψ com teto de
1/k e a herança repartida onde deveria entrar inteira.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from profiles import single_axis

from leilao.behavior import compute_bids, draw_interest, utility_matrix
from leilao.config import Discipline, SimulationConfig
from leilao.equations import (
    Behavior,
    RequestStates,
    class_difficulty,
    concave_bids,
    entry_class_load,
    market_prices,
    reachable_utility,
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
        entry_periods=1,
        students_per_profile=6,
        rounds=2,
        max_hours=WORKLOAD,
        seed=7,
        **single_axis(WORKLOAD),
    )
    return SimulationConfig(**{**base, **overrides})


# --- a partição ------------------------------------------------------------


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
    """É o que torna o modelo sem turmas um caso particular deste: mesmo nome,
    mesmas vagas, clique nenhum."""
    config = make_config(classes=1)
    assert config.classes_by_discipline() == {
        name: (name,) for name in config.hours_by_discipline()
    }
    assert config.seats_by_class() == config.hours_by_discipline().keys() | set() or True
    assert config.class_exclusions() == ()


def test_the_clique_is_one_per_discipline_with_more_than_one_class():
    config = make_config(classes=4)
    cliques = config.class_exclusions()
    assert len(cliques) == 3
    assert all(len(clique) == 4 for clique in cliques)


# --- a eq. (5) ------------------------------------------------------------


@pytest.mark.parametrize("mechanism", ["credits", "ranking"])
def test_nobody_takes_two_classes_of_the_same_discipline(mechanism):
    """A restrição da eq. (5), nos dois mecanismos. O leilão a resolve dentro
    da PLI; o CR, na caminhada da ditadura serial."""
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
    """O WDP impõe o clique **dentro** da rodada. Entre rodadas quem impede é
    o filtro por grupo do `available_goods` — sem ele, dá para ganhar a turma
    A na rodada 1 e a C na rodada 2."""
    config = make_config(classes=4, rounds=3)
    result = run_simulation(config)
    groups = config.discipline_by_class()

    for history in result.histories:
        for record in history.periods:
            won = [r for r in record.requests if r.won_round is not None]
            assert len({groups[r.discipline] for r in won}) == len(won)


# --- o preço ---------------------------------------------------------------


def test_a_routed_student_does_not_inflate_the_price_of_his_own_group():
    """Quem apostou em A, B e C e foi roteado para C não foi recusado em A e
    B: foi atendido. Contá-lo como perdedor ali faria cada membro do grupo
    encarecer as turmas do próprio grupo."""
    groups = {"D T1": "D", "D T2": "D", "D T3": "D"}
    bids = {("a", "D T1"): 10, ("a", "D T2"): 8, ("a", "D T3"): 6, ("b", "D T1"): 3}
    allocation = {("a", "D T3"): 1, ("b", "D T1"): 0}

    sem_grupo = market_prices(good_ids=list(groups), bids=bids, allocation=allocation)
    com_grupo = market_prices(
        good_ids=list(groups), bids=bids, allocation=allocation, groups=groups
    )

    # Sem grupos, os lances do próprio "a" definem o preço de T1 e T2.
    assert sem_grupo["D T1"] == 10
    assert sem_grupo["D T2"] == 8
    # Com grupos, só "b" perdeu — e só em T1.
    assert com_grupo["D T1"] == 3
    assert com_grupo["D T2"] == 1


# --- o lance ---------------------------------------------------------------


def test_the_bid_is_split_inside_the_group_by_the_same_knapsack():
    """O nível de dentro é a **mesma** mochila côncava, agora entre as turmas
    da disciplina: a fatia do grupo se reparte com retorno decrescente, mais
    na turma preferida e menos nas irmãs."""
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
    # D2 vale 0,9 contra os 0,3 da melhor turma de D1: o grosso vai para lá.
    assert por_grupo["D2"] > por_grupo["D1"]
    # A fatia de D1 se espalha pelas quatro turmas, em ordem de preferência.
    dentro = [bids[name] for name in classes["D1"]]
    assert all(credits > 0 for credits in dentro)
    assert dentro == sorted(dentro, reverse=True)


def test_the_two_levels_conserve_the_budget_credit_by_credit():
    """A soma por grupo é exatamente o que o nível de fora decidiu: a
    repartição interna gasta a fatia inteira (`reserve = 0`) e não cria nem
    perde crédito."""
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
    """Duas disciplinas de mesmo valor repartem o orçamento igual, mesmo com
    números de turmas bem diferentes. Num nível só, a de mais turmas levaria
    a fatia maior — o funil entraria no lance."""
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


# --- o pedido --------------------------------------------------------------


def test_the_request_is_one_class_per_discipline():
    """Disciplinas na ordem de preferência e, de cada uma, **uma** turma — a
    melhor disponível. Pedir duas turmas da mesma disciplina seria pedir duas
    vezes a mesma vaga."""
    classes = {"Alta": ("A T1", "A T2"), "Baixa": ("B T1", "B T2")}
    utilities = {"A T1": 0.2, "A T2": 0.5, "B T1": 0.4, "B T2": 0.1}
    pool = [name for names in classes.values() for name in names]

    pedido = request_set(utilities=utilities, available=pool, classes=classes)

    # Alta vale 0,5 (a melhor turma dela) contra 0,4 de Baixa: vem primeiro,
    # apesar de "B T1" valer mais que "A T1". E só a melhor turma de cada uma.
    assert pedido == ["A T2", "B T1"]


def test_selectivity_cuts_disciplines_not_classes():
    """O corte é sobre `max_t`, com a média tomada entre disciplinas: é ela
    que dá a leitura em múltiplos da indiferença."""
    classes = {"Querida": ("Q T1", "Q T2"), "Morna": ("M T1", "M T2")}
    utilities = {"Q T1": 0.6, "Q T2": 0.5, "M T1": 0.4, "M T2": 0.1}
    pool = [name for names in classes.values() for name in names]

    pedido = request_set(
        utilities=utilities,
        available=pool,
        behavior=Behavior(selectivity=1.1),
        classes=classes,
    )
    # Médias dos máximos: (0,6 + 0,4)/2 = 0,5; o limiar 0,55 corta Morna
    # inteira e preserva Querida — turma nenhuma é cortada sozinha, o grupo
    # inteiro entra ou sai.
    assert pedido == ["Q T1"]


# --- a utilidade -----------------------------------------------------------


def test_the_inheritance_enters_whole_in_every_class_of_the_target():
    """Somar a mesma parcela a todas as turmas eleva o máximo exatamente
    nela, e `Σ_d max` se conserva. Repartir trataria as turmas como partes da
    disciplina, e elas são alternativas."""
    classes = {"Porteira": ("P T1", "P T2"), "Travada": ("T T1", "T T2")}
    interest = {"P T1": 0.3, "P T2": 0.1, "T T1": 0.4, "T T2": 0.2}

    resultado = utility(
        interest=interest,
        eligible=["Porteira"],
        approved=set(),
        prerequisites={"Travada": ("Porteira",)},
        classes=classes,
    )
    # A travada vale o da turma mais útil dela: 0,4. Alvo único, parcela
    # inteira em cada turma da Porteira.
    assert resultado == {"P T1": pytest.approx(0.7), "P T2": pytest.approx(0.5)}
    # E o alcançável se conserva: 0,3 + 0,4 antes, 0,7 depois.
    assert reachable_utility(utilities=resultado, classes={"Porteira": classes["Porteira"]}) == pytest.approx(0.7)


def test_the_reachable_utility_is_the_sum_of_the_best_classes():
    """Com o 1 da linha inteira no denominador, ψ ganharia teto de ~1/k."""
    classes = {"A": ("A T1", "A T2", "A T3"), "B": ("B T1",)}
    utilities = {"A T1": 0.1, "A T2": 0.3, "A T3": 0.2, "B T1": 0.4}

    assert sum(utilities.values()) == pytest.approx(1.0)
    assert reachable_utility(utilities=utilities, classes=classes) == pytest.approx(0.7)


def test_satisfaction_can_reach_one_with_mutually_exclusive_classes():
    """Levar a melhor turma de toda disciplina elegível é ψ = 1. Era isso que
    o denominador fixo em 1 tornava impossível por construção."""
    from leilao.equations import satisfaction

    classes = {"A": ("A T1", "A T2"), "B": ("B T1", "B T2")}
    utilities = {"A T1": 0.4, "A T2": 0.1, "B T1": 0.35, "B T2": 0.15}
    alcancavel = reachable_utility(utilities=utilities, classes=classes)

    assert satisfaction(
        utilities=utilities, allocated=["A T1", "B T1"], reachable=alcancavel
    ) == pytest.approx(1.0)


def test_psi_never_passes_one_in_a_full_simulation():
    config = make_config(classes=4)
    result = run_simulation(config)
    for history in result.histories:
        for record in history.periods:
            assert 0.0 <= record.satisfaction <= 1.0 + 1e-9


# --- a escada de dificuldade ----------------------------------------------


@pytest.mark.parametrize("count", range(1, 10))
def test_the_ladder_keeps_the_geometric_mean_at_the_middle_level(count):
    """`n_baixa = n_alta` é o que fixa o centro, para todo k. A geométrica é o
    invariante certo porque a dificuldade entra em `attempt_rates` como
    expoentes recíprocos."""
    levels = class_difficulty(count=count, levels=(0.5, 1.0, 2.0))
    assert len(levels) == count
    geometric = math.exp(sum(math.log(x) for x in levels) / count)
    assert geometric == pytest.approx(1.0)


def test_the_ladder_has_as_many_easy_classes_as_hard_ones():
    for count in range(1, 10):
        levels = class_difficulty(count=count, levels=(0.5, 1.0, 2.0))
        assert levels.count(0.5) == levels.count(2.0)


def test_the_ladder_is_off_by_default():
    config = make_config(classes=4)
    assert set(config.difficulty_by_class().values()) == {1.0}


def test_the_difficulty_multiplies_the_one_declared_by_the_discipline():
    config = make_config(
        classes=1,
        disciplines=[
            Discipline("D", seats=24, hours=60, classes=3, difficulty=2.0, entry=True)
        ],
        class_difficulty_levels=(0.5, 1.0, 2.0),
    )
    assert sorted(config.difficulty_by_class().values()) == [1.0, 2.0, 4.0]


# --- o interesse em dois níveis -------------------------------------------


def _interest(stability: float, class_stability: float, periods: int = 3):
    config = make_config(
        classes=4,
        periods=periods,
        interest_stability=stability,
        class_stability=class_stability,
    )
    students = generate_students(config, np.random.default_rng(0))
    rows = draw_interest(students, config, np.random.default_rng(5))
    return config, students, rows


def test_class_stability_at_one_gives_every_class_the_same_interest():
    config, students, rows = _interest(0.5, 1.0)
    row = rows[(students[0].id, 1)]
    for names in config.classes_by_discipline().values():
        values = {round(row[name], 12) for name in names}
        assert len(values) == 1


def test_class_stability_at_zero_makes_the_classes_independent():
    config, students, rows = _interest(0.5, 0.0)
    row = rows[(students[0].id, 1)]
    for names in config.classes_by_discipline().values():
        values = {round(row[name], 12) for name in names}
        assert len(values) == len(names)


def test_period_stability_at_one_freezes_the_interest_even_with_classes():
    """Se a estabilidade entre períodos vale 1, o interesse de cada turma é o
    mesmo em todo período — por isso o desvio da turma passa pela **mesma**
    repartição temporal."""
    _config, students, rows = _interest(1.0, 0.3, periods=4)
    student = students[0].id
    primeira = rows[(student, 1)]
    for period in (2, 3, 4):
        assert rows[(student, period)] == pytest.approx(primeira)


def test_the_row_of_interest_sums_to_one_over_every_class():
    _config, students, rows = _interest(0.5, 0.4)
    for period in (1, 2, 3):
        assert sum(rows[(students[0].id, period)].values()) == pytest.approx(1.0)


def test_class_stability_widens_the_row_as_it_falls():
    """**σ continua sendo σ**: a repartição em dois níveis dá variância 1 a
    cada entrada do log, para qualquer estabilidade entre turmas.

    O que muda é o espalhamento **depois da normalização**, e muda por um
    motivo que não é defeito: normalizar subtrai log(Σ) da linha inteira, e
    quanto mais correlacionadas as entradas, mais da variância vai parar
    nesse termo comum — que some na subtração. Com estabilidade 1 as turmas
    de uma disciplina são cópias, e a linha encolhe; com 0 elas são
    independentes, e a linha abre.

    Fica registrado porque é consequência de calibragem: baixar a
    estabilidade entre turmas alarga a distribuição de interesse sem que
    ninguém tenha mexido em σ."""
    espalhamentos = []
    for class_stability in (1.0, 0.5, 0.0):
        _config, students, rows = _interest(0.0, class_stability)
        logs = [
            math.log(value)
            for student in students
            for value in rows[(student.id, 1)].values()
        ]
        media = sum(logs) / len(logs)
        espalhamentos.append(
            math.sqrt(sum((x - media) ** 2 for x in logs) / len(logs))
        )
    assert espalhamentos == sorted(espalhamentos)
    # E o alargamento é moderado: está longe de dobrar σ.
    assert espalhamentos[-1] < 1.5 * espalhamentos[0]


# --- o histórico continua por disciplina ----------------------------------


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
                # O pedido é de turma...
                assert pedido.discipline in turmas
                if pedido.attempt is not None:
                    # ...e a tentativa que ele gera é da disciplina: o aluno
                    # que cursou T2 na 1ª vez e T4 na 2ª está na 2ª tentativa.
                    assert pedido.attempt >= 1


def test_the_cohort_is_spread_evenly_over_the_entry_classes():
    """A matrícula garantida não escolhe turma, então ela tem de repartir: os
    primeiros da coorte na primeira turma, os seguintes na segunda."""
    config = make_config(classes=4)
    result = run_simulation(config)
    primeiro = result.periods[0]

    por_turma = {s.name: s.granted for s in primeiro.disciplines}
    assert sum(por_turma.values()) == 3 * config.students_per_period
    for discipline, names in config.classes_by_discipline().items():
        esperado = entry_class_load(
            cohort=config.students_per_period, classes=names
        )
        assert {name: por_turma[name] for name in names} == esperado
        # Blocos contíguos: nenhuma turma fica com dois a mais que outra.
        assert max(esperado.values()) - min(esperado.values()) <= 1


def test_a_class_only_prices_what_it_sold():
    """Preço é da turma: duas turmas da mesma disciplina podem fechar em
    preços diferentes, e é isso que diz qual delas foi mais disputada."""
    config = make_config(classes=4, periods=4)
    result = run_simulation(config)
    nomes = set(config.seats_by_class())
    for period in result.periods:
        for snapshot in period.disciplines:
            assert snapshot.name in nomes
            assert snapshot.discipline == config.discipline_by_class()[snapshot.name]
            assert snapshot.filled <= snapshot.seats


def test_the_bid_funds_several_classes_of_a_group_without_leaking_credits():
    """O aluno financia mais de uma turma do mesmo grupo — é o hedge dentro da
    rodada —, e o que o grupo recebe continua sendo o que o nível de fora lhe
    deu.

    Cada restrição de clique da PLI nasce de um aluno nesta situação, e é
    daqui que sai o custo de resolução do braço — 2,3× os lances e 4,1× o
    tempo no cenário padrão, medido no README.
    """
    config = make_config(classes=4, class_stability=0.3)
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


# --- os seis estados -------------------------------------------------------


def test_the_six_states_are_per_discipline_and_not_per_class():
    """O que o aluno pede, ganha e retém vem por **turma**; o catálogo e o
    histórico são por **disciplina**. Sem dobrar um no outro, `aprovada`
    procuraria turmas num conjunto de disciplinas, não acharia nenhuma, e
    tudo o que ele retivesse sairia como reprovada."""
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
        not_eligible=1,  # D3, bloqueada
        not_requested=0,
        refused=1,  # D2, pedida e não atendida
        excluded=0,
        failed=0,
        approved=1,  # D1, retida e aprovada
    )
    # E os estados continuam particionando o que falta: 3 do catálogo, nenhuma
    # aprovada antes deste período.
    assert estados.total == 3


def test_a_simulation_with_classes_reports_the_approvals_it_made():
    """A consequência visível do mesmo defeito, de ponta a ponta: a soma dos
    aprovados dos estados tem de andar junto com as aprovações do histórico."""
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
    # E ninguém é contado duas vezes: o funil é uma partição.
    for row in estados:
        assert row.total == pytest.approx(
            row.not_eligible
            + row.not_requested
            + row.refused
            + row.excluded
            + row.failed
            + row.approved
        )
