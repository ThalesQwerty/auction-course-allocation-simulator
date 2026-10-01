import numpy as np
import pytest

from leilao.behavior import compute_bids, draw_utilities, utility_matrix
from leilao.config import Course, Discipline, SimulationConfig
from leilao.grading import grade_for_attempt
from leilao.names import FIRST_NAMES, LAST_NAMES, sample_names
from leilao.population import Student


def make_config(**overrides) -> SimulationConfig:
    disciplines = [Discipline(f"D{i}", seats=5, hours=60) for i in range(1, 7)]
    return SimulationConfig(
        disciplines=disciplines,
        courses=[
            Course(
                "Curso",
                students_per_generation=3,
                hours_to_graduate=180,
                required=("D1", "D2", "D3"),
                electives=("D4", "D5"),
            )
        ],
        **overrides,
    )


def test_name_lists_have_256_unique_entries_each():
    assert len(FIRST_NAMES) == len(set(FIRST_NAMES)) == 256
    assert len(LAST_NAMES) == len(set(LAST_NAMES)) == 256


def test_sample_names_returns_distinct_full_names():
    names = sample_names(500, np.random.default_rng(0))
    assert len(names) == len(set(names)) == 500


def test_utility_matrix_respects_group_hierarchy_and_budget_fraction():
    config = make_config(periods=20)
    course = config.courses[0]
    student = Student("a1", "Fulano", "Curso", ability=0.5, credits=10)
    draws = draw_utilities([student], config, np.random.default_rng(3))

    for period in range(1, config.periods + 1):
        utilities = utility_matrix(
            draw=draws[("a1", period)], student=student, course=course, config=config
        )
        required = sum(utilities[name] for name in course.required)
        electives = sum(utilities[name] for name in course.electives)
        free = sum(utilities[name] for name in config.free_disciplines(course))
        # eqs. (47)-(48): obrigatórias >= optativas >= livres
        assert required >= electives >= free
        # eq. (43): U_a in (0, 1]
        assert 0 < sum(utilities.values()) <= 1
        # eq. (41): utilidades distintas entre si
        assert len(set(utilities.values())) == len(utilities)


def test_utility_matrix_ignores_approved_disciplines():
    config = make_config()
    student = Student("a1", "Fulano", "Curso", ability=0.5, credits=10, grades={"D1": 8.0})
    draws = draw_utilities([student], config, np.random.default_rng(1))
    utilities = utility_matrix(
        draw=draws[("a1", 1)], student=student, course=config.courses[0], config=config
    )
    assert "D1" not in utilities
    assert "D2" in utilities


def test_utility_matrix_is_a_pure_function_of_the_draw():
    """A matriz é parâmetro de entrada: o mesmo sorteio e o mesmo estado do
    aluno têm de dar sempre a mesma utilidade, chamados em qualquer ordem."""
    config = make_config()
    course = config.courses[0]
    student = Student("a1", "Fulano", "Curso", ability=0.5, credits=10)
    draw = draw_utilities([student], config, np.random.default_rng(5))[("a1", 1)]

    first = utility_matrix(draw=draw, student=student, course=course, config=config)
    other = Student("a2", "Beltrano", "Curso", ability=0.1, credits=10, grades={"D2": 9.0})
    utility_matrix(draw=draw, student=other, course=course, config=config)
    assert utility_matrix(draw=draw, student=student, course=course, config=config) == first


def test_approving_a_discipline_only_redistributes_its_utility():
    """Aprovar uma disciplina tira ela da matriz, mas as outras continuam
    vindo do mesmo sorteio — a preferência do aluno não é re-sorteada."""
    config = make_config()
    course = config.courses[0]
    draw = draw_utilities(
        [Student("a1", "Fulano", "Curso", ability=0.5, credits=10)],
        config,
        np.random.default_rng(9),
    )[("a1", 1)]

    before = utility_matrix(
        draw=draw,
        student=Student("a1", "Fulano", "Curso", ability=0.5, credits=10),
        course=course,
        config=config,
    )
    after = utility_matrix(
        draw=draw,
        student=Student("a1", "Fulano", "Curso", ability=0.5, credits=10, grades={"D1": 8.0}),
        course=course,
        config=config,
    )
    assert "D1" in before and "D1" not in after
    # Dentro das obrigatórias que sobraram, as proporções relativas se mantêm.
    assert after["D2"] / after["D3"] == pytest.approx(before["D2"] / before["D3"])


def test_bids_never_exceed_the_budget():
    utilities = {"D1": 0.4, "D2": 0.3, "D3": 0.1}
    bids = compute_bids(
        utilities=utilities, available=list(utilities), budget=10, spend_fraction=0.8
    )
    # eq. (19): a soma dos lances respeita o orçamento, e eqs. (44)-(46) gastam
    # exatamente floor(C_a * U_a).
    assert sum(bids.values()) == 8


def test_leftover_credits_go_to_the_most_preferred_disciplines():
    # Com 3 créditos para 3 disciplinas, cada lance preliminar é truncado para 1
    # e sobra 0; com 4 créditos, a sobra vai para a disciplina preferida.
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    bids = compute_bids(
        utilities=utilities, available=list(utilities), budget=4, spend_fraction=1.0
    )
    assert bids["D1"] > bids["D2"] >= bids.get("D3", 0)
    assert sum(bids.values()) == 4


def test_bids_only_consider_available_disciplines():
    utilities = {"D1": 0.5, "D2": 0.5}
    bids = compute_bids(utilities=utilities, available=["D2"], budget=10, spend_fraction=1.0)
    assert set(bids) == {"D2"}


def test_retake_raises_the_grade_by_the_learning_gain():
    assert grade_for_attempt(4.2, 1, 2.5) == 4.2
    assert grade_for_attempt(4.2, 2, 2.5) == 6.7
    assert grade_for_attempt(4.2, 3, 2.5) == 9.2
    # o ganho é configurável
    assert grade_for_attempt(4.2, 3, 1.0) == 6.2
    # a nota satura em 10
    assert grade_for_attempt(9.5, 3, 2.5) == 10.0
    with pytest.raises(ValueError):
        grade_for_attempt(5.0, 0, 2.5)
