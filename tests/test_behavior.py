import numpy as np
import pytest

from leilao.behavior import compute_bids, draw_utilities, utility_matrix
from leilao.config import DEFAULT_AFFINITY, DEFAULT_APTITUDE, Discipline, SimulationConfig
from leilao.grading import grade_for_attempt
from leilao.names import FIRST_NAMES, LAST_NAMES, sample_names
from leilao.population import Student


def make_config(**overrides) -> SimulationConfig:
    """Grade de três períodos: D1..D3 sem pré-requisito, D4..D6 encadeadas."""
    disciplines = [
        Discipline("D1", seats=5, hours=60),
        Discipline("D2", seats=5, hours=60),
        Discipline("D3", seats=5, hours=60),
        Discipline("D4", seats=5, hours=60, prerequisites=("D1",)),
        Discipline("D5", seats=5, hours=60, prerequisites=("D2", "D3")),
        Discipline("D6", seats=5, hours=60, prerequisites=("D4",)),
    ]
    return SimulationConfig(disciplines=disciplines, students_per_period=3, **overrides)


def student(**overrides) -> Student:
    """Um aluno nos perfis neutros: nota média e utilidade sem distorção. O que
    os perfis fazem é testado em `test_profiles.py`; aqui o que importa é o
    conjunto elegível."""
    base = dict(
        id="a1",
        name="Fulano",
        aptitude=DEFAULT_APTITUDE,
        affinity=DEFAULT_AFFINITY,
        credits=10,
    )
    return Student(**{**base, **overrides})


def test_name_lists_have_256_unique_entries_each():
    assert len(FIRST_NAMES) == len(set(FIRST_NAMES)) == 256
    assert len(LAST_NAMES) == len(set(LAST_NAMES)) == 256


def test_sample_names_returns_distinct_full_names():
    names = sample_names(500, np.random.default_rng(0))
    assert len(names) == len(set(names)) == 500


def test_curriculum_period_is_induced_from_the_prerequisites():
    """Sem pré-requisito é 1º período; com pré-requisitos é o maior deles mais
    um — a cadeia indutiva que substitui a senioridade da eq. (38)."""
    config = make_config()
    assert config.curriculum_periods() == {
        "D1": 1, "D2": 1, "D3": 1, "D4": 2, "D5": 2, "D6": 3
    }
    assert config.first_period_disciplines() == ["D1", "D2", "D3"]


def test_a_cycle_of_prerequisites_is_rejected():
    """Uma cadeia que se fecha não tem período nenhum: as disciplinas dela
    nunca ficariam elegíveis, e o cenário não se conclui por construção."""
    with pytest.raises(ValueError, match="ciclo de pré-requisitos"):
        SimulationConfig(
            disciplines=[
                Discipline("D1", seats=5, hours=60),
                Discipline("D2", seats=5, hours=60, prerequisites=("D3",)),
                Discipline("D3", seats=5, hours=60, prerequisites=("D2",)),
            ],
        )
    with pytest.raises(ValueError, match="pré-requisito de si mesma"):
        Discipline("D1", seats=5, hours=60, prerequisites=("D1",))


def test_unknown_prerequisite_is_rejected():
    with pytest.raises(ValueError, match="pré-requisitos inexistentes"):
        SimulationConfig(
            disciplines=[Discipline("D1", seats=5, hours=60, prerequisites=("D9",))]
        )


def test_utility_matrix_covers_only_the_eligible_disciplines():
    """eq. (42): só entra o que o aluno ainda precisa cursar *e* já pode — a
    bloqueada por pré-requisito vale zero tanto quanto a já aprovada."""
    config = make_config(periods=20)
    novice = student()
    draws = draw_utilities([novice], config, np.random.default_rng(3))

    for period in range(1, config.periods + 1):
        utilities = utility_matrix(draw=draws[("a1", period)], student=novice, config=config)
        # Quem não aprovou nada só alcança o 1º período da grade.
        assert set(utilities) == {"D1", "D2", "D3"}
        # eq. (43): U_a in (0, 1]
        assert 0 < sum(utilities.values()) <= 1
        # eq. (41): utilidades distintas entre si
        assert len(set(utilities.values())) == len(utilities)


def test_approving_a_prerequisite_unlocks_the_next_discipline():
    config = make_config()
    draw = draw_utilities([student()], config, np.random.default_rng(1))[("a1", 1)]

    before = utility_matrix(draw=draw, student=student(), config=config)
    after = utility_matrix(
        draw=draw, student=student(grades={"D1": 8.0}), config=config
    )
    # D1 sai (aprovada) e D4 entra (pré-requisito cumprido); D6 continua fora,
    # porque depende de D4.
    assert set(before) == {"D1", "D2", "D3"}
    assert set(after) == {"D2", "D3", "D4"}


def test_a_failed_prerequisite_does_not_unlock_anything():
    """Cursar não basta: a eq. (42) exige aprovação — n_{a,x} >= n_min."""
    config = make_config()
    draw = draw_utilities([student()], config, np.random.default_rng(7))[("a1", 1)]
    failed = student(grades={"D1": 4.9}, attempts={"D1": 1})
    assert set(utility_matrix(draw=draw, student=failed, config=config)) == {"D1", "D2", "D3"}


def test_utility_matrix_is_a_pure_function_of_the_draw():
    """A matriz é parâmetro de entrada: o mesmo sorteio e o mesmo estado do
    aluno têm de dar sempre a mesma utilidade, chamados em qualquer ordem."""
    config = make_config()
    draw = draw_utilities([student()], config, np.random.default_rng(5))[("a1", 1)]

    first = utility_matrix(draw=draw, student=student(), config=config)
    utility_matrix(draw=draw, student=student(id="a2", grades={"D2": 9.0}), config=config)
    assert utility_matrix(draw=draw, student=student(), config=config) == first


def test_approving_a_discipline_only_redistributes_its_utility():
    """Aprovar uma disciplina tira ela da matriz, mas as outras continuam
    vindo do mesmo sorteio — a preferência do aluno não é re-sorteada."""
    config = make_config()
    draw = draw_utilities([student()], config, np.random.default_rng(9))[("a1", 1)]

    before = utility_matrix(draw=draw, student=student(), config=config)
    # D3 aprovada: D1 e D2 continuam elegíveis, e D5 não entra (falta D2).
    after = utility_matrix(draw=draw, student=student(grades={"D3": 8.0}), config=config)
    assert "D3" in before and "D3" not in after
    assert after["D1"] / after["D2"] == pytest.approx(before["D1"] / before["D2"])


def test_an_empty_eligible_set_gives_no_utility():
    """Quem aprovou a grade inteira não quer mais nada — e, por isso, já se
    formou antes de chegar a um leilão."""
    config = make_config()
    draw = draw_utilities([student()], config, np.random.default_rng(2))[("a1", 1)]
    done = student(grades={name: 9.0 for name in ("D1", "D2", "D3", "D4", "D5", "D6")})
    assert utility_matrix(draw=draw, student=done, config=config) == {}


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


def test_bid_proportions_do_not_depend_on_the_utility_scale():
    """O que a utilidade zerada fora do elegível torna redundante: o lance usa
    só razões entre utilidades, então multiplicar a matriz inteira por uma
    constante não muda lance nenhum. U_a pesa só como fração do orçamento."""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    scaled = {name: value * 7 for name, value in utilities.items()}
    common = dict(available=list(utilities), budget=20, spend_fraction=0.9)
    assert compute_bids(utilities=utilities, **common) == compute_bids(
        utilities=scaled, **common
    )


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
