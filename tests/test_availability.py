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
    Discipline,
    DEFAULT_AVAILABILITY,
    DEFAULT_PERFORMANCE,
    AvailabilityShape,
    PerformanceShape,
    SimulationConfig,
)
from leilao.equations import (
    RequestStates,
    split_normal_mean,
    effective_load,
    exclusion_rate,
    exclusion_refund,
    request_funnel,
    request_states,
    retained_set,
)
from leilao.grading import GradeShapes, draw_base_quantiles, grade_for_attempt
from leilao.population import Student, generate_students
from leilao.simulation.snapshots import Axis
from leilao.equations import quantile_names
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
        students_per_period=18,
        # A referência da escala é `1/(turmas da grade)` — aqui 4 disciplinas
        # de turma única —, que põe o limiar na utilidade média de uma
        # elegível. Ver `equations.reserve_threshold`.
        selectivity_median=0.25,
        quantiles=3,
        rounds=2,
        max_hours=240,
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


def test_excluding_refunds_nothing_by_default():
    """O padrão é o crédito gasto se perder por inteiro. Sem isso, com o
    retorno desligado (k = 0) excluir seria o melhor resultado possível do
    sistema: nada se perderia e a vaga ainda assim não voltaria à oferta."""
    for paid in range(0, 21):
        assert exclusion_refund(paid=paid) == 0


def test_the_exclusion_rate_scales_the_price_paid():
    """A fração é do cenário e é a única coisa que devolve crédito à excluída."""
    assert exclusion_refund(paid=10, rate=0.5) == 5
    assert exclusion_refund(paid=10, rate=1.0) == 10
    assert exclusion_refund(paid=7, rate=0.5) == 4
    # Fração pequena zera em lance pequeno, que é o lance mais frequente.
    assert exclusion_refund(paid=1, rate=0.25) == 0
    assert exclusion_refund(paid=4, rate=0.25) == 1
    # Excluir nunca devolve mais do que se pagou: a fração é limitada a [0, 1]
    # na configuração, e aqui a conta respeita o limite.
    for paid in range(1, 21):
        assert exclusion_refund(paid=paid, rate=1.0) == paid

    with pytest.raises(ValueError, match="negativo"):
        exclusion_refund(paid=-1)


def test_the_scenario_refuses_an_exclusion_rate_outside_the_unit_interval():
    """Acima de 1 excluir renderia mais que o lance; abaixo de 0 não é fração."""
    for rate in (-0.1, 1.5):
        with pytest.raises(ValueError, match="fração de retorno da exclusão"):
            make_config(exclusion_refund_rate=rate)


def test_the_exclusion_rate_reaches_the_simulation():
    """A fração do cenário é a que o fechamento do período aplica."""
    sem = run_simulation(make_config(exclusion_refund_rate=0.0))
    com = run_simulation(make_config(exclusion_refund_rate=1.0))

    excluidos = [
        (sem_req, com_req)
        for sem_h, com_h in zip(sem.histories, com.histories)
        for sem_p, com_p in zip(sem_h.periods, com_h.periods)
        for sem_req, com_req in zip(sem_p.requests, com_p.requests)
        if sem_req.excluded
    ]
    assert excluidos, "o cenário deveria ter exclusões"
    assert all(s.returned == 0 for s, _ in excluidos)
    assert all(c.returned == c.paid for _, c in excluidos)


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


# --- as quatro frações do funil --------------------------------------------


def test_each_funnel_share_divides_by_the_node_before_it():
    """Cada fração responde por um nó, e o denominador é o que chegou até
    ali — não o catálogo."""
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
    # Pediu 8 das 15 que lhe faltavam.
    assert funnel.requested_share == pytest.approx(8 / 15)
    # Das 8 pedidas, 6 foram deferidas.
    assert funnel.granted_share == pytest.approx(6 / 8)
    # Das 6 deferidas, cursou 5.
    assert funnel.attended_share == pytest.approx(5 / 6)
    # Das 5 cursadas, passou em 3.
    assert funnel.approved_share == pytest.approx(3 / 5)


def test_an_empty_node_gives_none_and_never_zero():
    """"Ninguém pediu nada" é diferente de "ninguém foi deferido" — e zero
    diria a segunda coisa."""
    nothing = request_funnel(RequestStates(5, 5, 0, 0, 0, 0))
    assert nothing.requested_share == 0.0
    assert nothing.granted_share is None
    assert nothing.attended_share is None
    assert nothing.approved_share is None
    assert request_funnel(RequestStates(0, 0, 0, 0, 0, 0)).requested_share is None


def test_the_attended_share_is_the_complement_of_the_exclusion_rate():
    """A redundância é exata, e é bom que esteja declarada: a fração de
    cursadas é `1 − ε`, as duas vindas das mesmas contagens."""
    states = RequestStates(2, 2, 1, 3, 4, 5)
    funnel = request_funnel(states)
    allocated = int(states.excluded + states.failed + states.approved)
    assert funnel.attended_share == pytest.approx(
        1 - exclusion_rate(excluded=int(states.excluded), allocated=allocated)
    )


# --- os eixos da população -------------------------------------------------


def test_the_cohort_is_typed_not_derived():
    """O tamanho da coorte é digitado. Era derivado do produto das combinações
    de perfil até 19/11/2026, e mexer num eixo mudava a população sem que
    ninguém pedisse."""
    config = make_config(students_per_period=20)
    students = generate_students(config, np.random.default_rng(0))
    assert config.students_per_period == 20
    assert len([s for s in students if s.entry_period == 1]) == 20


def test_the_quantile_bands_split_the_population_evenly():
    """O corte é teórico, não amostral: `Φ(nível)` é uniforme por construção,
    então as faixas saem com o mesmo tamanho esperado e as **fronteiras são as
    mesmas em toda execução** — sem isso a média entre seeds somaria faixas
    que não são a mesma coisa."""
    config = make_config(students_per_period=150, quantiles=4)
    students = generate_students(config, np.random.default_rng(0))
    axis = Axis.quantiles(config)["performance"]
    assert axis.order == ["0–25%", "25–50%", "50–75%", "75–100%"]

    counts = Counter(axis.key(s) for s in students)
    esperado = len(students) / 4
    for name in axis.order:
        assert abs(counts[name] - esperado) < 0.15 * esperado, name


def test_one_band_is_the_whole_university():
    config = make_config(quantiles=1)
    axis = Axis.quantiles(config)["selectivity"]
    assert axis.order == ["Geral"]
    students = generate_students(config, np.random.default_rng(0))
    assert {axis.key(s) for s in students} == {"Geral"}


def test_the_base_levels_come_from_the_seed():
    """Ao contrário dos perfis, que eram atribuídos por posição, o nível
    basilar é sorteado: duas seeds dão populações diferentes, que é o que a
    Seção 7.3 quer quando pede múltiplas configurações de entrada."""
    config = make_config()
    one = generate_students(config, np.random.default_rng(1))
    two = generate_students(config, np.random.default_rng(99))
    assert [s.performance_level for s in one] != [s.performance_level for s in two]
    # O período de ingresso continua fora da seed.
    assert [s.entry_period for s in one] == [s.entry_period for s in two]


def test_the_base_level_gives_the_cr_a_floor_to_disperse_around():
    """Sem nível basilar a média dos quantis de um aluno converge para 0,5: a
    dispersão cai como 1/√D e **não tem piso**. Com ele, o que sobra depois de
    muitas disciplinas é o nível, e a ordenação por CR continua ordenando.

    O teste compara a mesma medida em duas grades de tamanhos diferentes: é
    onde a diferença entre "cai" e "tem piso" aparece.
    """
    config = make_config(students_per_period=150)
    students = generate_students(config, np.random.default_rng(0))

    def spread(stability: float, materias: int) -> float:
        cfg = make_config(students_per_period=150, performance_stability=stability)
        grade = [
            Discipline(name=f"M{i}", seats=10, hours=60) for i in range(materias)
        ]
        quantis = draw_base_quantiles(students, grade, cfg, np.random.default_rng(1))
        por_aluno: dict[str, list[float]] = {}
        for (student_id, _), value in quantis.items():
            por_aluno.setdefault(student_id, []).append(value)
        medias = [sum(v) / len(v) for v in por_aluno.values()]
        return float(np.std(medias))

    # Sem nível basilar, quadruplicar a grade corta a dispersão pela metade.
    assert spread(0.0, 40) < 0.6 * spread(0.0, 10)
    # Com ele, ela mal se move: o que sobra é o aluno.
    assert spread(0.8, 40) > 0.9 * spread(0.8, 10)
    # E em qualquer tamanho ela é maior.
    assert spread(0.8, 40) > 2 * spread(0.0, 40)


def test_the_marginal_of_the_quantile_stays_uniform():
    """O nível basilar reparte a variância, não a muda: a calibragem da nota
    não se move com ele."""
    config = make_config(students_per_period=150, performance_stability=0.6)
    students = generate_students(config, np.random.default_rng(0))
    valores = list(
        draw_base_quantiles(students, GRADE, config, np.random.default_rng(1)).values()
    )
    assert np.mean(valores) == pytest.approx(0.5, abs=0.02)
    assert np.std(valores) == pytest.approx(1 / np.sqrt(12), abs=0.02)


def test_the_summary_carries_the_band_of_the_student():
    """A tela individual é onde se pergunta "por que *este* aluno foi assim",
    e a faixa é metade da resposta — a seed é a outra."""
    config = make_config()
    result = run_simulation(config)
    faixas = set(quantile_names(config.quantiles))

    assert result.students
    for summary in result.students:
        assert summary.performance in faixas
        assert summary.availability in faixas
        assert summary.selectivity in faixas


def test_a_student_built_by_hand_sits_at_the_median():
    """Quem constrói um aluno à mão não está escolhendo uma ponta."""
    student = Student(id="x", name="X", credits=10)
    assert student.performance_level == 0.0
    assert student.availability_level == 0.0
    assert student.selectivity_level == 0.0


def test_the_scenario_rejects_distributions_that_do_not_exist():
    # A moda tem de caber abaixo de W_a: com o pico no teto não existe
    # log-normal que ainda o alcance com a frequência pedida.
    with pytest.raises(ValueError, match="abaixo da carga"):
        make_config(availability=AvailabilityShape(240.0, 0.1))
    with pytest.raises(ValueError, match="chance"):
        make_config(availability=AvailabilityShape(200.0, 1.0))
    # No desempenho a moda sempre cabe; o que pode não caber são as chances.
    with pytest.raises(ValueError, match="escala"):
        make_config(
            performance=PerformanceShape(
                mode_grade=10.0, zero_rate=0.01, max_rate=0.01
            )
        )
    with pytest.raises(ValueError, match="quantis"):
        make_config(quantiles=9)
    with pytest.raises(ValueError, match="nível basilar"):
        make_config(performance_stability=1.5)


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
    # O valor varia entre os períodos — o nível basilar é o patamar em torno
    # do qual ele flutua, não um valor fixo repetido.
    reduced = min(students, key=lambda s: s.availability_level)
    row = [drawn[(reduced.id, t)] for t in range(1, config.periods + 1)]
    assert len(set(row)) == len(row)


def test_tripling_the_seats_moves_no_availability_draw():
    """A mesma invariante que o interesse tem: nada é sorteado
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
        make_config(availability=always_available(240))
    )
    for history in result.histories:
        for record in history.periods:
            assert record.retained_hours == record.enrolled_hours
            assert not any(r.excluded for r in record.requests)
