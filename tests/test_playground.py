"""O playground é o laço de uma alocação, com a elegibilidade dada à mão."""

import pytest

from leilao.behavior import compute_bids
from leilao.equations import Behavior
from leilao.playground import PlaygroundClass, PlaygroundStudent, run_playground
from leilao.ranking import request_set


def discipline(name: str, seats: int = 1, hours: int = 60) -> PlaygroundClass:
    """Disciplina de turma única: a turma é a própria disciplina."""
    return PlaygroundClass(name, seats, hours)


def turmas(group: str, count: int, seats: int = 1, hours: int = 60) -> list[PlaygroundClass]:
    return [
        PlaygroundClass(f"{group} T{i}", seats, hours, group) for i in range(1, count + 1)
    ]


def student(
    student_id: str,
    *,
    utilities: dict[str, float],
    eligible: list[str] | None = None,
    credits: int = 10,
    cr: float = 0,
    max_hours: int = 120,
    availability: float | None = None,
    selectivity: float = 0.0,
    concentration: float = 1.0,
) -> PlaygroundStudent:
    return PlaygroundStudent(
        student_id,
        credits,
        cr,
        max_hours,
        utilities,
        tuple(eligible if eligible is not None else utilities),
        availability=availability,
        selectivity=selectivity,
        concentration=concentration,
    )


def test_auction_bids_match_the_knapsack_and_the_higher_bid_takes_the_seat():
    disciplines = [discipline("A")]
    ana = student("ana", utilities={"A": 4}, credits=5, max_hours=60)
    bia = student("bia", utilities={"A": 1}, credits=3, max_hours=60)
    result = run_playground(
        mechanism="credits",
        rounds=1,
        seed=1,
        classes=disciplines,
        students=[ana, bia],
    )
    round_ = result.rounds[0]
    by_id = {row.id: row for row in round_.students}
    assert by_id["ana"].bids == compute_bids(
        utilities={"A": 4}, available=["A"], budget=5
    )
    assert by_id["bia"].bids == {"A": 3}
    assert by_id["ana"].won == ("A",)
    assert by_id["bia"].won == ()
    assert round_.prices == {"A": 3}
    assert by_id["ana"].remaining_credits == 2
    assert by_id["bia"].remaining_credits == 3


def test_the_higher_cr_takes_the_last_seat():
    result = run_playground(
        mechanism="ranking",
        rounds=1,
        seed=2,
        classes=[discipline("A")],
        students=[
            student("baixo", utilities={"A": 9}, cr=4, max_hours=60),
            student("alto", utilities={"A": 1}, cr=9, max_hours=60),
        ],
    )
    by_id = {row.id: row for row in result.rounds[0].students}
    assert by_id["alto"].won == ("A",)
    assert by_id["baixo"].won == ()
    assert result.rounds[0].prices is None
    assert by_id["alto"].remaining_credits is None


def test_an_ineligible_discipline_is_not_bid_even_with_high_utility():
    result = run_playground(
        mechanism="credits",
        rounds=1,
        seed=3,
        classes=[discipline("Querida", seats=2), discipline("Marcada", seats=2)],
        students=[
            student(
                "ana",
                utilities={"Querida": 100, "Marcada": 1},
                eligible=["Marcada"],
                credits=4,
                max_hours=120,
            )
        ],
    )
    assert result.rounds[0].students[0].bids == {"Marcada": 4}
    assert result.rounds[0].students[0].utilities == {"Marcada": pytest.approx(1)}
    assert result.rounds[0].students[0].won == ("Marcada",)


def test_the_second_round_skips_what_was_won_and_what_no_longer_fits():
    """Quatro créditos cabem todos na utilidade alta. A segunda rodada só vê a
    outra disciplina, e com a carga que sobrou."""
    result = run_playground(
        mechanism="credits",
        rounds=2,
        seed=4,
        classes=[discipline("A"), discipline("B")],
        students=[
            student(
                "ana",
                utilities={"A": 100, "B": 1},
                credits=4,
                max_hours=120,
            )
        ],
    )
    first, second = result.rounds
    assert first.students[0].bids == {"A": 4}
    assert first.students[0].utilities == {"A": pytest.approx(100 / 101), "B": pytest.approx(1 / 101)}
    assert second.students[0].utilities == first.students[0].utilities
    assert first.students[0].won == ("A",)
    assert first.students[0].remaining_hours == 60
    assert second.students[0].bids == {"B": 3}
    assert "A" not in second.students[0].bids
    assert second.students[0].won == ("B",)
    assert second.students[0].remaining_hours == 0


def test_grades_are_seeded_and_only_cover_what_was_won():
    kwargs = dict(
        mechanism="ranking",
        rounds=1,
        seed=11,
        classes=[discipline("A", seats=1), discipline("B", seats=1)],
        students=[
            student("ana", utilities={"A": 2, "B": 1}, cr=8, max_hours=60),
        ],
    )
    first = run_playground(**kwargs)
    second = run_playground(**kwargs)
    assert first.grades == second.grades
    assert [grade.name for grade in first.grades] == ["A"]
    assert all(0 <= grade.grade <= 10 for grade in first.grades)

    other = run_playground(**{**kwargs, "seed": 12})
    assert other.grades != first.grades


def test_a_non_positive_utility_is_rejected():
    with pytest.raises(ValueError, match="número positivo"):
        run_playground(
            mechanism="credits",
            rounds=1,
            seed=0,
            classes=[discipline("A")],
            students=[student("ana", utilities={"A": 0}, credits=1, max_hours=60)],
        )


def test_the_bid_reads_the_student_behavior():
    """Seletividade e concentração entram no lance como na simulação."""
    utilities = {"A": 6, "B": 3, "C": 1}
    behavior = Behavior(concentration=2.0, selectivity=0.5)
    result = run_playground(
        mechanism="credits",
        rounds=1,
        seed=5,
        classes=[discipline("A"), discipline("B"), discipline("C")],
        students=[
            student(
                "ana",
                utilities=utilities,
                credits=12,
                max_hours=180,
                selectivity=behavior.selectivity,
                concentration=behavior.concentration,
            )
        ],
    )
    expected = compute_bids(
        utilities=utilities, available=["A", "B", "C"], budget=12, behavior=behavior
    )
    assert result.rounds[0].students[0].bids == expected
    assert "C" not in expected
    assert expected != compute_bids(
        utilities=utilities, available=["A", "B", "C"], budget=12
    )


def test_selectivity_also_cuts_the_ranking_request():
    utilities = {"A": 10, "B": 1}
    result = run_playground(
        mechanism="ranking",
        rounds=1,
        seed=6,
        classes=[discipline("A"), discipline("B")],
        students=[student("ana", utilities=utilities, cr=7, selectivity=1.0)],
    )
    asked = request_set(
        utilities=utilities, available=["A", "B"], behavior=Behavior(selectivity=1.0)
    )
    assert asked == ["A"]
    assert list(result.rounds[0].students[0].bids) == asked
    assert result.rounds[0].students[0].won == ("A",)


def test_what_does_not_fit_the_availability_is_excluded_and_ungraded():
    """O especulador pede as duas e obtém as duas; com 60 h disponíveis leva a
    mais útil e larga a outra, que não recebe nota."""
    result = run_playground(
        mechanism="ranking",
        rounds=1,
        seed=7,
        classes=[discipline("A"), discipline("B")],
        students=[
            student("ana", utilities={"A": 1, "B": 3}, cr=7, availability=60)
        ],
    )
    assert result.rounds[0].students[0].won == ("A", "B")
    (closing,) = result.closing
    assert closing.load == 60
    assert closing.retained == ("B",)
    assert closing.excluded == ("A",)
    assert [grade.name for grade in result.grades] == ["B"]


def test_without_availability_nothing_is_excluded():
    result = run_playground(
        mechanism="ranking",
        rounds=1,
        seed=8,
        classes=[discipline("A"), discipline("B")],
        students=[student("ana", utilities={"A": 1, "B": 3}, cr=7)],
    )
    (closing,) = result.closing
    assert closing.load is None
    assert closing.retained == ("A", "B")
    assert closing.excluded == ()


def test_excluding_does_not_move_anyone_elses_grade():
    def grades(availability: float) -> dict[tuple[str, str], float]:
        result = run_playground(
            mechanism="ranking",
            rounds=1,
            seed=9,
            classes=[discipline("A", seats=2), discipline("B", seats=2)],
            students=[
                student("ana", utilities={"A": 1, "B": 3}, cr=8, availability=availability),
                student("bia", utilities={"A": 2, "B": 1}, cr=6),
            ],
        )
        return {(g.student_id, g.name): g.grade for g in result.grades}

    full, cut = grades(120), grades(60)
    assert ("ana", "A") in full and ("ana", "A") not in cut
    assert {k: v for k, v in full.items() if k[0] == "bia"} == {
        k: v for k, v in cut.items() if k[0] == "bia"
    }


def test_a_negative_selectivity_is_rejected():
    with pytest.raises(ValueError, match="seletividade"):
        run_playground(
            mechanism="credits",
            rounds=1,
            seed=0,
            classes=[discipline("A")],
            students=[student("ana", utilities={"A": 1}, selectivity=-1)],
        )


def test_the_auction_splits_between_the_classes_and_never_takes_two():
    """Mochila em dois níveis: a fatia da disciplina se reparte entre as
    turmas dela, com mais na preferida — e o clique (eq. 5) concede uma só,
    de modo que na rodada seguinte o grupo inteiro já saiu do disponível."""
    classes = turmas("Cálculo", 2) + [discipline("Física")]
    utilities = {"Cálculo T1": 3, "Cálculo T2": 2, "Física": 1}
    result = run_playground(
        mechanism="credits",
        rounds=2,
        seed=10,
        classes=classes,
        students=[student("ana", utilities=utilities, credits=8, max_hours=180)],
    )
    first, second = result.rounds
    groups = {"Cálculo": ("Cálculo T1", "Cálculo T2"), "Física": ("Física",)}
    assert first.students[0].bids == compute_bids(
        utilities=utilities,
        available=list(utilities),
        budget=8,
        classes=groups,
    )
    lances = first.students[0].bids
    assert lances["Cálculo T1"] > lances["Cálculo T2"] > 0
    assert first.students[0].won == ("Cálculo T1", "Física")
    assert second.students[0].bids == {}
    assert first.students[0].remaining_hours == 60


def test_the_ranking_sends_the_loser_to_the_sister_class_next_round():
    """Os dois pedem só a T1, que é a melhor turma dos dois: o CR mais alto a
    leva, e quem perdeu só chega à T2 na rodada seguinte, quando
    `available_goods` devolve a irmã. O seguro é a rodada, não o pedido."""
    result = run_playground(
        mechanism="ranking",
        rounds=2,
        seed=11,
        classes=turmas("Cálculo", 2),
        students=[
            student("alto", utilities={"Cálculo T1": 3, "Cálculo T2": 1}, cr=9),
            student("baixo", utilities={"Cálculo T1": 3, "Cálculo T2": 1}, cr=5),
        ],
    )
    first, second = result.rounds
    by_id = {row.id: row for row in first.students}
    assert list(by_id["alto"].bids) == ["Cálculo T1"]
    assert list(by_id["baixo"].bids) == ["Cálculo T1"]
    assert by_id["alto"].won == ("Cálculo T1",)
    assert by_id["baixo"].won == ()

    by_id = {row.id: row for row in second.students}
    assert list(by_id["alto"].bids) == []
    assert list(by_id["baixo"].bids) == ["Cálculo T2"]
    assert by_id["baixo"].won == ("Cálculo T2",)


def test_the_ranking_never_grants_two_classes_of_the_same_discipline():
    result = run_playground(
        mechanism="ranking",
        rounds=2,
        seed=12,
        classes=turmas("Cálculo", 2, seats=5),
        students=[student("ana", utilities={"Cálculo T1": 1, "Cálculo T2": 1}, cr=7)],
    )
    won = [name for round_ in result.rounds for name in round_.students[0].won]
    assert won == ["Cálculo T1"]


def test_the_grade_is_of_the_discipline_not_of_the_class():
    """O quantil é da disciplina: cursar a T1 ou a T2 dá a mesma nota."""

    def grade(utilities: dict[str, float]) -> float:
        result = run_playground(
            mechanism="ranking",
            rounds=1,
            seed=13,
            classes=turmas("Cálculo", 2),
            students=[student("ana", utilities=utilities, cr=7)],
        )
        (only,) = result.grades
        return only.grade

    assert grade({"Cálculo T1": 2, "Cálculo T2": 1}) == grade(
        {"Cálculo T1": 1, "Cálculo T2": 2}
    )
