"""O playground é o laço de uma alocação, com a elegibilidade dada à mão."""

import pytest

from leilao.behavior import compute_bids
from leilao.playground import PlaygroundDiscipline, PlaygroundStudent, run_playground


def discipline(name: str, seats: int = 1, hours: int = 60) -> PlaygroundDiscipline:
    return PlaygroundDiscipline(name, seats, hours)


def student(
    student_id: str,
    *,
    utilities: dict[str, float],
    eligible: list[str] | None = None,
    credits: int = 10,
    cr: float = 0,
    max_hours: int = 120,
) -> PlaygroundStudent:
    return PlaygroundStudent(
        student_id,
        credits,
        cr,
        max_hours,
        utilities,
        tuple(eligible if eligible is not None else utilities),
    )


def test_auction_bids_match_the_knapsack_and_the_higher_bid_takes_the_seat():
    disciplines = [discipline("A")]
    ana = student("ana", utilities={"A": 4}, credits=5, max_hours=60)
    bia = student("bia", utilities={"A": 1}, credits=3, max_hours=60)
    result = run_playground(
        mechanism="credits",
        rounds=1,
        seed=1,
        disciplines=disciplines,
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
        disciplines=[discipline("A")],
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
        disciplines=[discipline("Querida", seats=2), discipline("Marcada", seats=2)],
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
        disciplines=[discipline("A"), discipline("B")],
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
        disciplines=[discipline("A", seats=1), discipline("B", seats=1)],
        students=[
            student("ana", utilities={"A": 2, "B": 1}, cr=8, max_hours=60),
        ],
    )
    first = run_playground(**kwargs)
    second = run_playground(**kwargs)
    assert first.grades == second.grades
    assert [grade.discipline for grade in first.grades] == ["A"]
    assert all(0 <= grade.grade <= 10 for grade in first.grades)

    other = run_playground(**{**kwargs, "seed": 12})
    assert other.grades != first.grades


def test_a_non_positive_utility_is_rejected():
    with pytest.raises(ValueError, match="número positivo"):
        run_playground(
            mechanism="credits",
            rounds=1,
            seed=0,
            disciplines=[discipline("A")],
            students=[student("ana", utilities={"A": 0}, credits=1, max_hours=60)],
        )
