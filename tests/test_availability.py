"""Disponibilidade, exclusão e os dois eixos de perfil.

As três peças que entraram juntas: o sorteio da fração de W_a que o aluno de
fato cursa, a mochila do que ele leva e o que a exclusão faz com o crédito, a
nota e a tentativa.
"""
from __future__ import annotations

import numpy as np
import pytest

from profiles import always_available
from disciplines import disciplines_from_predecessors

from leilao.availability import draw_availability
from leilao.config import (
    DEFAULT_AVAILABILITY,
    DEFAULT_PERFORMANCE,
    AvailabilityProfile,
    PerformanceProfile,
    SimulationConfig,
)
from leilao.equations import (
    RequestStates,
    split_normal_mean,
    effective_load,
    exclusion_rate,
    exclusion_refund,
    request_states,
    retained_set,
)
from leilao.grading import GradeShapes, draw_base_quantiles, grade_for_attempt
from leilao.population import Student, generate_students
from leilao.simulation import run_simulation

GRADE = disciplines_from_predecessors(
    ("D1", 20, 60),
    ("D2", 20, 60),
    ("D3", 12, 90, ("D1",)),
    ("D4", 12, 90, ("D2",)),
)


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=6,
        entry_periods=3,
        max_residence=4,
        students_per_period=9,
        rounds=2,
        max_hours=240,
        credit_return="ratio",
        seed=7,
    )
    return SimulationConfig(**{**base, **overrides})


# --- carga efetiva ---------------------------------------------------------


def test_the_effective_load_rounds_to_the_nearest_hour():
    """A disponibilidade já vem em horas: a carga efetiva só arredonda."""
    assert effective_load(availability=360.0) == 360
    assert effective_load(availability=180.4) == 180
    assert effective_load(availability=0.0) == 0
    # O round do Python desempata para o par, como no retorno de créditos.
    assert effective_load(availability=319.5) == 320


def test_the_effective_load_has_no_ceiling():
    """O teto de carga é do **sistema**, não do aluno, e por isso a carga
    efetiva não clipa em W_a. Quem tem tempo para mais do que o curso oferece
    simplesmente não exclui nada — quem impede a matrícula é o alocador, que
    nunca entrega mais que W_a durante as rodadas."""
    assert effective_load(availability=500.0) == 500


def test_the_effective_load_rejects_a_negative_availability():
    with pytest.raises(ValueError):
        effective_load(availability=-1.0)


# --- a mochila do que ele leva ---------------------------------------------


def test_the_knapsack_beats_dropping_by_ascending_utility():
    """O contraexemplo que justifica a mochila: a heurística sacrifica duas
    disciplinas baratas para salvar uma cara.

    Teto 122 h, obtidas Algoritmos (90 h, u 0,22), Cálculo (60 h, 0,13) e
    Física (60 h, 0,11). Tirando da menor utilidade para a maior sobra só
    Algoritmos, com 0,22 retido; a mochila fica com Cálculo + Física, 120 h e
    0,24.
    """
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
    """Mesma regra do resto do motor: utilidades empatadas resolvem pela ordem
    da grade, e não pela ordem de iteração."""
    utilities = {"primeira": 0.2, "segunda": 0.2}
    hours = {"primeira": 60, "segunda": 60}
    assert retained_set(
        utilities=utilities, hours=hours, obtained=utilities, load=60
    ) == ["primeira"]
    # E a saída sai na ordem da grade, não na da conta.
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


# --- o retorno da exclusão -------------------------------------------------


def test_excluding_always_costs_at_least_one_credit():
    """A divisão inteira é o que garante custo. Ancorar na maior nota que
    reprova devolveria o crédito inteiro de um lance de 1 com n_min >= 6, que
    é justamente o lance mais frequente."""
    for paid in range(1, 21):
        refund = exclusion_refund("ratio", paid=paid)
        assert refund < paid
        assert paid - refund >= 1


def test_only_the_proportional_policy_refunds_an_exclusion():
    """As outras três só pagam por aprovação, e excluir não aprova. Sem isso,
    sob `none` — em que nada volta nunca — excluir seria o melhor resultado
    possível do sistema."""
    assert exclusion_refund("ratio", paid=10) == 5
    for policy in ("none", "unit", "full"):
        assert exclusion_refund(policy, paid=10) == 0


# --- o desperdício ---------------------------------------------------------


def test_the_exclusion_rate_is_zero_when_nothing_was_allocated():
    """Recorte sem vaga obtida não desperdiçou nada — o que é diferente de
    não haver ninguém, que o recorte vazio já trata não publicando métrica."""
    assert exclusion_rate(excluded=0, allocated=0) == 0.0
    assert exclusion_rate(excluded=3, allocated=12) == 0.25
    with pytest.raises(ValueError):
        exclusion_rate(excluded=4, allocated=3)


# --- os seis estados -------------------------------------------------------


def test_the_six_states_partition_what_is_still_missing():
    """Cada disciplina que ainda falta cai em exatamente um estado, e a soma é
    o tamanho do denominador."""
    states = request_states(
        catalogue=["A", "B", "C", "D", "E", "F"],
        approved={"A", "D"},  # A vinha de antes; D passou agora
        eligible=["B", "C", "D"],
        requested={"B", "D"},
        won={"B", "D"},
        retained={"D"},
    )
    assert states == RequestStates(
        not_eligible=2,  # E e F, bloqueadas
        not_requested=1,  # C
        refused=0,
        excluded=1,  # B, obtida e largada
        failed=0,
        approved=1,  # D
    )
    # O catálogo tem 6; A já estava aprovada e sai do denominador.
    assert states.total == 5


def test_the_already_approved_leave_the_denominator():
    """É o que impede "não elegível" de crescer por progresso e encolher por
    desbloqueio ao mesmo tempo, cancelando-se."""
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
    assert depois.total == 1  # A saiu: não é mais algo que lhe falta
    assert depois.not_eligible == 0


def test_the_average_is_per_student_and_never_a_sum():
    rows = [
        RequestStates(4, 2, 0, 1, 0, 1),
        RequestStates(2, 2, 0, 1, 2, 1),
    ]
    assert RequestStates.average(rows) == RequestStates(3, 2, 0, 1, 1, 1)
    assert RequestStates.average([]) == RequestStates(0, 0, 0, 0, 0, 0)


# --- os perfis -------------------------------------------------------------


def test_the_combinations_split_the_generation_equally():
    """Com 3 perfis em cada eixo são 9 pares, e cada um fica com ~1/9 da
    geração. Não há porcentagem a configurar."""
    config = make_config(students_per_period=18)
    students = generate_students(config, np.random.default_rng(0))
    first = [s for s in students if s.entry_period == 1]
    assert len(first) == 18

    pairs = [(s.performance.name, s.availability.name) for s in first]
    assert len(set(pairs)) == 9
    assert all(pairs.count(pair) == 2 for pair in set(pairs))


def test_the_profile_does_not_come_from_the_seed():
    """Mesmo motivo do período de ingresso: duas execuções com seeds
    diferentes têm a mesma estrutura de grupos, então a diferença entre elas
    não é quem calhou de ser frágil."""
    config = make_config()
    one = generate_students(config, np.random.default_rng(1))
    two = generate_students(config, np.random.default_rng(99))
    assert [s.performance.name for s in one] == [s.performance.name for s in two]
    assert [s.availability.name for s in one] == [s.availability.name for s in two]
    # O que muda com a seed é o nome — e, fora daqui, os dois escalares.
    assert [s.name for s in one] != [s.name for s in two]


def test_the_leftover_of_an_uneven_generation_rotates_between_generations():
    """Com geração que não é múltipla do número de pares, o excedente gira em
    vez de cair sempre nos mesmos primeiros pares."""
    config = make_config(students_per_period=10, entry_periods=3)
    students = generate_students(config, np.random.default_rng(0))
    by_generation = [
        [
            (s.performance.name, s.availability.name)
            for s in students
            if s.entry_period == period
        ]
        for period in (1, 2, 3)
    ]
    extras = [
        {pair for pair in set(gen) if gen.count(pair) == 2} for gen in by_generation
    ]
    assert all(len(e) == 1 for e in extras)
    assert extras[0] != extras[1] != extras[2]


def test_the_grade_follows_the_profile_of_each_student():
    """A heterogeneidade é sistemática: há grupos a separar, e não só
    dispersão. O quantil sorteado é o mesmo uniforme para todo mundo — quem
    separa os grupos é a **distribuição** em que ele é lido."""
    config = make_config()
    students = [
        Student(
            id=f"{group}-{i:03d}",
            name=f"Aluno {group}{i}",
            credits=10,
            performance=profile,
        )
        for group, profile in enumerate(DEFAULT_PERFORMANCE)
        for i in range(400)
    ]
    quantiles = draw_base_quantiles(students, GRADE, config, np.random.default_rng(0))
    shapes = GradeShapes()

    by_student = {s.id: s.performance for s in students}
    for profile in DEFAULT_PERFORMANCE:
        mode, left_sd, right_sd = shapes.of(profile, 1.0, 1)
        # A média é derivada da forma, não é o parâmetro: o perfil declara a
        # moda, e a cauda esquerda longa puxa a média para baixo dela.
        expected_mean = split_normal_mean(
            mode=mode, left_sd=left_sd, right_sd=right_sd
        )
        drawn = [
            grade_for_attempt(
                quantile=value, mode=mode, left_sd=left_sd, right_sd=right_sd
            )
            for (student_id, _), value in quantiles.items()
            if by_student[student_id] is profile
        ]
        assert abs(sum(drawn) / len(drawn) - expected_mean) < 0.1


def test_the_summary_carries_both_profiles_of_the_student():
    """A tela individual é onde se pergunta "por que *este* aluno foi assim",
    e o perfil é metade da resposta — a seed é a outra."""
    config = make_config()
    result = run_simulation(config)
    desempenho = {p.name for p in config.performance_profiles}
    disponibilidade = {p.name for p in config.availability_profiles}

    assert result.students
    for summary in result.students:
        assert summary.performance in desempenho
        assert summary.availability in disponibilidade
    # A repartição igualitária aparece no resumo, não só na população.
    pares = {(s.performance, s.availability) for s in result.students}
    assert len(pares) == config.profile_combinations()


def test_a_student_built_by_hand_gets_the_neutral_profile():
    """Quem constrói um aluno à mão não está escolhendo um grupo: herdar o
    primeiro da lista enviesaria o teste sem avisar."""
    student = Student(id="x", name="X", credits=10)
    assert student.performance.name == "—"
    assert student.availability.name == "—"
    assert student.performance not in DEFAULT_PERFORMANCE
    assert student.availability not in DEFAULT_AVAILABILITY


def test_the_scenario_rejects_profiles_that_would_not_describe_a_group():
    with pytest.raises(ValueError, match="pelo menos um perfil"):
        make_config(performance_profiles=())
    with pytest.raises(ValueError, match="únicos"):
        make_config(
            availability_profiles=(
                AvailabilityProfile("igual", 200.0, 0.1),
                AvailabilityProfile("igual", 150.0, 0.1),
            )
        )
    # A moda tem de caber abaixo de W_a: com o pico no teto não existe
    # log-normal que ainda o alcance com a frequência pedida.
    with pytest.raises(ValueError, match="abaixo da carga"):
        make_config(availability_profiles=(AvailabilityProfile("no teto", 240.0, 0.1),))
    with pytest.raises(ValueError, match="chance"):
        make_config(availability_profiles=(AvailabilityProfile("certa", 200.0, 1.0),))
    # No desempenho a moda sempre cabe; o que pode não caber são as chances.
    with pytest.raises(ValueError, match="escala"):
        make_config(
            performance_profiles=(
                PerformanceProfile("fora", mode_grade=10.0, zero_rate=0.01,
                                   max_rate=0.01),
            )
        )


# --- o sorteio -------------------------------------------------------------


def test_availability_is_drawn_once_per_student_and_period():
    """Ao contrário do desempenho, que é um só para o curso inteiro: o tempo
    disponível é circunstância, não traço. O que é traço é a forma."""
    config = make_config()
    students = generate_students(config, np.random.default_rng(0))
    drawn = draw_availability(students, config, np.random.default_rng(0))

    assert len(drawn) == len(students) * config.periods
    # Em horas, não em fração: a log-normal nunca desce a zero e não tem teto,
    # de modo que passar de W_a é legítimo.
    assert all(value > 0.0 for value in drawn.values())
    assert any(value > config.max_hours for value in drawn.values())
    # Um aluno de disponibilidade reduzida varia entre os períodos — não é
    # um valor fixo repetido.
    reduced = next(s for s in students if s.availability.name.startswith("Baixa"))
    row = [drawn[(reduced.id, t)] for t in range(1, config.periods + 1)]
    assert len(set(row)) == len(row)


def test_tripling_the_seats_moves_no_availability_draw():
    """A mesma invariante que a matriz de utilidades tem: nada é sorteado
    dentro do laço, senão mexer numa vaga mudaria o comportamento de todo
    mundo e a diferença entre dois cenários deixaria de ser do mecanismo."""
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


# --- o que a exclusão faz na simulação inteira -----------------------------


def test_excluding_costs_no_attempt_and_leaves_the_record_without_a_grade():
    """Quem exclui e refaz no semestre seguinte volta como primeira
    tentativa, sem o ganho de recursada."""
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
    """Exclui-se depois de encerradas as alocações do período, então a vaga
    morre com quem a pegou. É o que torna a exclusão socialmente cara."""
    result = run_simulation(make_config())
    for period in result.periods:
        for snapshot in period.disciplines:
            # `filled` conta a vaga consumida, excluída ou não.
            assert snapshot.exclusions <= snapshot.filled
            assert snapshot.filled <= snapshot.seats


def test_the_waste_is_the_gap_between_the_two_utilizations():
    """A ocupação fica no alocado e o aproveitamento efetivo no retido; a
    diferença entre os dois é o desperdício, e é o que a disponibilidade
    existe para produzir."""
    result = run_simulation(make_config())
    measured = [
        period.aggregate.overall.metrics
        for period in result.periods
        if period.aggregate.overall.metrics is not None
    ]
    assert measured
    for metrics in measured:
        assert metrics.effective_utilization <= metrics.utilization
        assert metrics.excluded <= metrics.allocated
        assert metrics.exclusion_rate == pytest.approx(
            metrics.excluded / metrics.allocated if metrics.allocated else 0.0
        )
    assert any(m.excluded > 0 for m in measured)


def test_a_full_availability_scenario_never_excludes():
    """Com disponibilidade praticamente cheia a mecânica some, e o modelo
    volta a ser o de antes dela — o controle que separa o efeito da exclusão
    de tudo o mais que mudou junto.

    Note o que uma chance de encher tão alta custa à forma: com a moda logo
    abaixo de W_a, exigir que 99,99% da massa fique **acima** dele força um
    desvio logarítmico enorme, e a mediana vai para a casa dos milhões de
    horas. É consistente, e para este controle é exatamente o que se quer —
    mas mostra que "quase sempre cheio" e "tipicamente perto de W_a" são
    pedidos incompatíveis nesta família.
    """
    result = run_simulation(
        make_config(availability_profiles=always_available(240))
    )
    for history in result.histories:
        for record in history.periods:
            assert record.retained_hours == record.enrolled_hours
            assert not any(r.excluded for r in record.requests)
