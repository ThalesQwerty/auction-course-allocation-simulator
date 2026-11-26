import numpy as np
import pytest

from profiles import single_axis
from disciplines import disciplines_from_predecessors
from leilao.behavior import (
    NEUTRAL,
    Behavior,
    compute_bids,
    decide,
    draw_interest,
    utility_matrix,
)
from leilao.config import Discipline, SimulationConfig
from leilao.equations import attempt_approval
from leilao.names import FIRST_NAMES, LAST_NAMES, sample_names
from leilao.population import Student, generate_students


def make_config(**overrides) -> SimulationConfig:
    """Grade de três períodos: D1..D3 de entrada, D4..D6 encadeadas."""
    disciplines = disciplines_from_predecessors(
        ("D1", 5, 60),
        ("D2", 5, 60),
        ("D3", 5, 60),
        ("D4", 5, 60, ("D1",)),
        ("D5", 5, 60, ("D2", "D3")),
        ("D6", 5, 60, ("D4",)),
    )
    base = dict(
        disciplines=disciplines, students_per_entry_class=3, max_hours=360, **single_axis(360)
    )
    return SimulationConfig(**{**base, **overrides})


def student(**overrides) -> Student:
    """Um aluno qualquer: o que importa aqui é o conjunto elegível dele. O"""
    base = dict(id="a1", name="Fulano", credits=10)
    return Student(**{**base, **overrides})


def test_name_lists_have_256_unique_entries_each():
    assert len(FIRST_NAMES) == len(set(FIRST_NAMES)) == 256
    assert len(LAST_NAMES) == len(set(LAST_NAMES)) == 256


def test_sample_names_returns_distinct_full_names():
    names = sample_names(500, np.random.default_rng(0))
    assert len(names) == len(set(names)) == 500


def test_curriculum_period_and_height_are_induced_from_unlocks():
    """Período conta do ingresso (aresta inversa); altura, dos sucessores."""
    config = make_config()
    assert config.curriculum_periods() == {
        "D1": 1, "D2": 1, "D3": 1, "D4": 2, "D5": 2, "D6": 3
    }
    assert config.heights() == {
        "D1": 2, "D2": 1, "D3": 1, "D4": 1, "D5": 0, "D6": 0
    }
    assert config.entry_disciplines() == ["D1", "D2", "D3"]


def test_a_root_without_the_entry_flag_stays_eligible():
    """Sem pré-requisito não é entrada. A raiz livre entra no conjunto elegível"""
    config = SimulationConfig(
        disciplines=disciplines_from_predecessors(
            ("Entrada", 5, 60),
            ("Livre", 5, 60, False),
            ("Seguinte", 5, 60, ("Entrada",)),
        ),
        students_per_entry_class=2,
        max_hours=120,
        **single_axis(120),
    )
    assert config.entry_disciplines() == ["Entrada"]
    assert config.curriculum_periods()["Livre"] == 1
    assert set(config.eligible_disciplines(set())) == {"Entrada", "Livre"}


def test_an_entry_discipline_cannot_have_a_prerequisite():
    with pytest.raises(ValueError, match="pré-requisitos"):
        SimulationConfig(
            disciplines=disciplines_from_predecessors(
                ("Base", 5, 60),
                ("Depende", 5, 60, ("Base",), True),
            ),
            students_per_entry_class=2,
            max_hours=120,
            **single_axis(120),
        )


def test_a_scenario_without_entry_disciplines_is_rejected():
    with pytest.raises(ValueError, match="disciplina de entrada"):
        SimulationConfig(
            disciplines=disciplines_from_predecessors(("Livre", 5, 60, False)),
            students_per_entry_class=1,
            max_hours=60,
            **single_axis(60),
        )


def test_a_cycle_of_unlocks_is_rejected():
    """Uma cadeia que se fecha não tem altura nem período: as disciplinas dela"""
    with pytest.raises(ValueError, match="ciclo de sucessores"):
        SimulationConfig(
            disciplines=[
                Discipline("D1", seats=5, hours=60),
                Discipline("D2", seats=5, hours=60, unlocks=("D3",)),
                Discipline("D3", seats=5, hours=60, unlocks=("D2",)),
            ],
        )
    with pytest.raises(ValueError, match="sucessora de si mesma"):
        Discipline("D1", seats=5, hours=60, unlocks=("D1",))


def test_unknown_successor_is_rejected():
    with pytest.raises(ValueError, match="sucessores inexistentes"):
        SimulationConfig(
            disciplines=[Discipline("D1", seats=5, hours=60, unlocks=("D9",))]
        )


def test_the_interest_matrix_reads_as_the_dictionary_it_replaced():
    """`InterestMatrix` guarda o array e monta a linha no acesso — 131 MB no"""
    config = make_config(periods=4)
    students = [student(id=f"a{i}") for i in range(3)]
    rows = draw_interest(students, config, np.random.default_rng(0))

    assert len(rows) == 3 * 4
    assert set(rows) == {(s.id, p) for s in students for p in range(1, 5)}
    assert list(rows.values()) == [rows[key] for key in rows]


def test_the_period_of_the_interest_matrix_is_one_based():
    """O eixo do array é 0-based e a chave é 1-based. O que não pode acontecer"""
    config = make_config(periods=4)
    rows = draw_interest([student(id="a0")], config, np.random.default_rng(0))

    assert rows[("a0", 1)] and rows[("a0", 4)]
    for ausente in [("a0", 0), ("a0", -1), ("a0", 5), ("fulano", 1)]:
        with pytest.raises(KeyError):
            rows[ausente]


def test_the_interest_row_is_built_fresh_at_each_access():
    """A linha é montada, não guardada — então escrever nela não alcança a"""
    config = make_config(periods=2)
    rows = draw_interest([student(id="a0")], config, np.random.default_rng(0))

    linha = rows[("a0", 1)]
    assert linha == rows[("a0", 1)]
    assert linha is not rows[("a0", 1)]

    nome = next(iter(linha))
    linha[nome] = 999.0
    assert rows[("a0", 1)][nome] != 999.0


def test_the_drawn_row_is_taste_alone_and_sums_to_one():
    """A invariante de altura saiu: a posição na grade **não** ordena mais o"""
    config = make_config(periods=4)
    students = [student(id=f"a{i}") for i in range(5)]
    rows = draw_interest(students, config, np.random.default_rng(0))
    heights = config.heights()

    assert all(all(v > 0 for v in row.values()) for row in rows.values())
    inverted = any(
        row[x] < row[y]
        for row in rows.values()
        for x, y in [(a, b) for a in row for b in row if heights[a] > heights[b]]
    )
    assert inverted


def test_utility_matrix_covers_only_the_eligible_disciplines():
    """eq. (42): só entra o que o aluno ainda precisa cursar *e* já pode — a"""
    config = make_config(periods=20)
    novice = student()
    row = draw_interest([novice], config, np.random.default_rng(3))[("a1", 1)]

    utilities = utility_matrix(interest=row, student=novice, config=config)
    assert set(utilities) == {"D1", "D2", "D3"}
    assert len(set(utilities.values())) == len(utilities)
    assert sum(utilities.values()) == pytest.approx(1.0)


def test_approving_a_prerequisite_unlocks_the_next_discipline():
    config = make_config()
    row = draw_interest([student()], config, np.random.default_rng(1))[("a1", 1)]

    before = utility_matrix(interest=row, student=student(), config=config)
    after = utility_matrix(interest=row, student=student(grades={"D1": 8.0}), config=config)
    assert set(before) == {"D1", "D2", "D3"}
    assert set(after) == {"D2", "D3", "D4"}


def test_a_failed_prerequisite_does_not_unlock_anything():
    """Cursar não basta: a eq. (42) exige aprovação — n_{a,x} >= n_apr."""
    config = make_config()
    row = draw_interest([student()], config, np.random.default_rng(7))[("a1", 1)]
    failed = student(grades={"D1": 4.9}, attempts={"D1": 1})
    assert set(utility_matrix(interest=row, student=failed, config=config)) == {"D1", "D2", "D3"}


def test_utility_matrix_is_a_pure_function_of_the_row():
    """A matriz é parâmetro de entrada: a mesma linha e o mesmo estado do aluno"""
    config = make_config()
    row = draw_interest([student()], config, np.random.default_rng(5))[("a1", 1)]

    first = utility_matrix(interest=row, student=student(), config=config)
    utility_matrix(interest=row, student=student(id="a2", grades={"D2": 9.0}), config=config)
    assert utility_matrix(interest=row, student=student(), config=config) == first


def test_approving_a_discipline_concentrates_the_inheritance_on_who_is_left():
    """Aprovar D3 tira a disciplina da matriz e deixa D5 — que ela e D2"""
    config = make_config()
    row = draw_interest([student()], config, np.random.default_rng(9))[("a1", 1)]

    before = utility_matrix(interest=row, student=student(), config=config)
    after = utility_matrix(interest=row, student=student(grades={"D3": 8.0}), config=config)
    assert "D3" in before and "D3" not in after
    assert sum(before.values()) == pytest.approx(1.0)
    assert sum(after.values()) == pytest.approx(1.0)
    assert after["D2"] / after["D1"] > before["D2"] / before["D1"]


def test_an_empty_eligible_set_gives_no_utility():
    """Quem aprovou a grade inteira não quer mais nada — e, por isso, já se"""
    config = make_config()
    row = draw_interest([student()], config, np.random.default_rng(2))[("a1", 1)]
    done = student(grades={name: 9.0 for name in ("D1", "D2", "D3", "D4", "D5", "D6")})
    assert utility_matrix(interest=row, student=done, config=config) == {}


def _harmonic_value(bids: dict[str, int], utilities: dict[str, float]) -> float:
    """O que o aluno extrai de uma repartição: c créditos em x valem u_x vezes o"""
    return sum(
        utilities[name] * sum(1.0 / step for step in range(1, credits + 1))
        for name, credits in bids.items()
    )


def _splits(total: int, parts: int):
    """Todas as formas de repartir `total` créditos inteiros entre `parts`"""
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in _splits(total - first, parts - 1):
            yield (first, *rest)


def test_bids_spend_the_whole_budget():
    """Não há poupança de créditos: todo crédito a mais tem ganho marginal"""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    for budget in range(1, 16):
        bids = compute_bids(utilities=utilities, available=list(utilities), budget=budget)
        assert sum(bids.values()) == budget
        assert all(credits > 0 for credits in bids.values())


def test_the_marginal_utility_decays_with_each_extra_credit():
    """O N-ésimo crédito numa disciplina vale u_x / N, e é isso que decide a"""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    common = dict(utilities=utilities, available=list(utilities))
    assert compute_bids(**common, budget=1) == {"D1": 1}
    assert compute_bids(**common, budget=2) == {"D1": 1, "D2": 1}
    assert compute_bids(**common, budget=3) == {"D1": 2, "D2": 1}
    assert compute_bids(**common, budget=4) == {"D1": 2, "D2": 1, "D3": 1}


def test_a_large_budget_still_reaches_the_least_preferred_discipline():
    """O decaimento é o que impede o aluno de despejar tudo na preferida: com"""
    utilities = {"D1": 0.7, "D2": 0.2, "D3": 0.1}
    bids = compute_bids(utilities=utilities, available=list(utilities), budget=20)
    assert set(bids) == {"D1", "D2", "D3"}
    assert bids["D1"] > bids["D2"] > bids["D3"]


def test_the_greedy_split_matches_an_exhaustive_search():
    """O guloso é ótimo porque os pesos são unitários e o ganho marginal cai"""
    utilities = {"D1": 0.44, "D2": 0.31, "D3": 0.17, "D4": 0.08}
    names = list(utilities)
    for budget in range(1, 10):
        bids = compute_bids(utilities=utilities, available=names, budget=budget)
        best = max(
            _harmonic_value(dict(zip(names, split)), utilities)
            for split in _splits(budget, len(names))
        )
        assert _harmonic_value(bids, utilities) == pytest.approx(best)


def test_the_greedy_split_with_a_reserve_matches_an_exhaustive_search():
    """Com piso, o guloso resolve `max Σ u·H(c) − s·Σ c`: o crédito vale o que
    rende menos o que a opção externa pagaria por ele.
    """
    utilities = {"D1": 0.44, "D2": 0.31, "D3": 0.17, "D4": 0.08}
    names = list(utilities)
    perfil = Behavior(selectivity=0.3)
    reserve = 0.3 / (0.3 + 1.0)
    for budget in range(1, 10):
        bids = compute_bids(
            utilities=utilities,
            available=names,
            budget=budget,
            behavior=perfil,
            interest=1.0,
        )
        best = max(
            _harmonic_value(dict(zip(names, split)), utilities) - reserve * sum(split)
            for spent in range(budget + 1)
            for split in _splits(spent, len(names))
        )
        liquido = _harmonic_value(bids, utilities) - reserve * sum(bids.values())
        assert liquido == pytest.approx(best)


def test_the_reserve_cuts_the_class_inside_the_discipline():
    """O piso vale nos dois níveis: a turma abaixo da reserva não recebe crédito
    mesmo com a disciplina dela admitida, e o que sobra fica poupado.
    """
    classes = {"D": ("D T1", "D T2")}
    utilities = {"D T1": 0.6, "D T2": 0.4}
    comum = dict(utilities=utilities, available=list(utilities), classes=classes)

    assert compute_bids(
        **comum, budget=3, behavior=Behavior(selectivity=0.5), interest=0.5
    ) == {"D T1": 1}
    assert compute_bids(**comum, budget=3) == {"D T1": 2, "D T2": 1}


def test_the_first_level_gain_is_the_best_available_class():
    """O ganho da disciplina é a melhor turma **obtenível**: a turma sem vaga
    não pontua por ela, senão o primeiro nível destinaria crédito que o segundo
    não teria onde gastar.
    """
    classes = {"D": ("D T1", "D T2"), "E": ("E T1",)}
    utilities = {"D T1": 0.9, "D T2": 0.2, "E T1": 0.5}

    assert compute_bids(
        utilities=utilities,
        available=["D T2", "E T1"],
        budget=1,
        classes=classes,
    ) == {"E T1": 1}
    assert compute_bids(
        utilities=utilities,
        available=list(utilities),
        budget=1,
        classes=classes,
    ) == {"D T1": 1}


def test_a_tie_goes_to_the_discipline_listed_first():
    """Empate de utilidade é resolvido pela ordem global de desempate: a ordem"""
    tied = {"D1": 0.25, "D2": 0.25, "D3": 0.25, "D4": 0.25}
    assert compute_bids(utilities=tied, available=list(tied), budget=2) == {
        "D1": 1,
        "D2": 1,
    }
    reversed_grade = {name: 0.25 for name in ("D4", "D3", "D2", "D1")}
    assert compute_bids(
        utilities=reversed_grade, available=["D1", "D2", "D3", "D4"], budget=2
    ) == {"D4": 1, "D3": 1}


def test_available_may_arrive_in_any_order():
    """`available` é um filtro, não uma ordenação: embaralhá-lo não muda lance"""
    tied = {"D1": 0.25, "D2": 0.25, "D3": 0.25, "D4": 0.25}
    straight = compute_bids(utilities=tied, available=["D1", "D2", "D3", "D4"], budget=3)
    shuffled = compute_bids(utilities=tied, available=["D3", "D1", "D4", "D2"], budget=3)
    assert straight == shuffled == {"D1": 1, "D2": 1, "D3": 1}


def test_a_tie_between_marginal_gains_also_follows_the_grade_order():
    """O empate pode surgir entre utilidades diferentes: o 2º crédito de uma"""
    utilities = {"D1": 0.4, "D2": 0.2}
    assert compute_bids(utilities=utilities, available=list(utilities), budget=2) == {
        "D1": 2
    }
    flipped = {"D2": 0.2, "D1": 0.4}
    assert compute_bids(utilities=flipped, available=list(flipped), budget=2) == {
        "D1": 1,
        "D2": 1,
    }


def test_bids_only_consider_available_disciplines():
    utilities = {"D1": 0.5, "D2": 0.5}
    bids = compute_bids(utilities=utilities, available=["D2"], budget=10)
    assert bids == {"D2": 10}


def test_without_pool_or_budget_there_is_no_bid():
    utilities = {"D1": 0.5, "D2": 0.5}
    assert compute_bids(utilities=utilities, available=[], budget=10) == {}
    assert compute_bids(utilities=utilities, available=list(utilities), budget=0) == {}


def test_bid_proportions_do_not_depend_on_the_utility_scale():
    """A mochila côncava compara só razões entre utilidades — u_x/N contra"""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    scaled = {name: value * 7 for name, value in utilities.items()}
    common = dict(available=list(utilities), budget=20)
    assert compute_bids(utilities=utilities, **common) == compute_bids(
        utilities=scaled, **common
    )


def test_the_retake_only_raises_the_approval_rate():
    """Repetir move a chance de aprovar para cima e nunca para baixo, porque o"""
    def rate(previous, gain=1.0):
        return attempt_approval(
            approval_rate=0.5, repetition_gain=gain, previous_attempts=previous
        )

    assert rate(0) < rate(1) < rate(2) < rate(3)
    assert rate(0) == 0.5
    assert rate(0, gain=0.0) == rate(5, gain=0.0) == 0.5
    assert rate(2, gain=0.5) == rate(1, gain=1.0)
    with pytest.raises(ValueError):
        rate(-1)


def test_a_utility_row_sums_to_one_over_the_whole_curriculum():
    """A linha inteira vale 1, e é essa invariante que `metrics.satisfaction`"""
    config = make_config()
    rng = np.random.default_rng(config.seed)
    students = generate_students(config, rng)
    rows = draw_interest(students, config, rng)
    assert rows, "nenhuma linha sorteada"
    for row in rows.values():
        assert set(row) == {d.name for d in config.disciplines}
        assert all(value > 0 for value in row.values())
    for student_ in students[:3]:
        utilities = utility_matrix(
            interest=rows[(student_.id, 1)], student=student_, config=config
        )
        assert sum(utilities.values()) == pytest.approx(1.0)


def test_the_message_is_the_utility_itself():
    """Não há expoente a aplicar: a mensagem do aluno **é** a utilidade dele,"""
    utilities = {"D1": 0.4, "D2": 0.3, "D3": 0.2, "D4": 0.1}
    pool = list(utilities)
    assert compute_bids(
        utilities=utilities, available=pool, budget=10
    ) == compute_bids(
        utilities=utilities, available=pool, budget=10, behavior=NEUTRAL
    )
    _admitted, scores, _reserve = decide(utilities=utilities)
    assert scores == utilities


def test_the_bid_is_proportional_to_the_utility():
    """Com orçamento que acomode o arredondamento, os créditos saem na razão"""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    bids = compute_bids(utilities=utilities, available=list(utilities), budget=20)
    assert bids == {"D1": 10, "D2": 6, "D3": 4}


def test_the_reserve_is_the_share_of_the_outside_option():
    """A reserva e a fatia que a opcao externa fica no bolo:"""
    utilities = {"D1": 0.6, "D2": 0.4}

    admitted, _scores, reserve = decide(
        utilities=utilities, behavior=Behavior(selectivity=1.0), interest=1.0
    )
    assert reserve == pytest.approx(0.5)
    assert set(admitted) == {"D1"}

    folgado, _scores, solto = decide(
        utilities=utilities, behavior=Behavior(selectivity=0.25), interest=1.0
    )
    assert solto == pytest.approx(0.2)
    assert set(folgado) == {"D1", "D2"}


def test_without_eligible_interest_there_is_no_reserve():
    """Sem elegiveis o limiar sai 0, e nao 1: nao ha o que cortar."""
    _admitted, _scores, reserve = decide(
        utilities={"D1": 0.6}, behavior=Behavior(selectivity=2.0), interest=0.0
    )
    assert reserve == 0.0


def test_selectivity_survives_the_catalogue_growing():
    """O corte e em multiplos da indiferenca, e nao absoluto: dobrar o"""
    base = [0.20, 0.16, 0.13, 0.11, 0.09, 0.08, 0.07, 0.06, 0.05, 0.05]
    pequeno = {f"D{i}": value for i, value in enumerate(base)}
    grande = {f"G{i}": value / 2 for i, value in enumerate(base + base)}

    perfil = Behavior(selectivity=0.1)
    fracao_pequeno = len(
        decide(utilities=pequeno, behavior=perfil, interest=1.0)[0]
    ) / len(pequeno)
    fracao_grande = len(
        decide(utilities=grande, behavior=perfil, interest=2.0)[0]
    ) / len(grande)
    assert abs(fracao_pequeno - fracao_grande) < 0.05

    absoluto = 0.1 / (0.1 + 1.0)
    acima = sum(1 for value in grande.values() if value >= absoluto)
    assert acima / len(grande) < 0.2


def test_the_reserve_also_stops_the_spending():
    """A diferenca em relacao ao filtro sozinho: com limiar 0,5 e score 0,6, o"""
    utilities = {"D1": 0.6, "D2": 0.4}
    pool = list(utilities)

    full = compute_bids(utilities=utilities, available=pool, budget=20)
    assert set(full) == {"D1", "D2"}
    assert sum(full.values()) == 20

    picky = compute_bids(
        utilities=utilities, available=pool, budget=20,
        behavior=Behavior(selectivity=1.0), interest=1.0,
    )
    assert set(picky) == {"D1"}
    assert sum(picky.values()) == 1


def test_the_neutral_profile_spends_everything():
    """Seletividade 0 desliga o corte e a parada: o laco roda o orcamento"""
    bids = compute_bids(
        utilities={"D1": 0.6, "D2": 0.4}, available=["D1", "D2"], budget=20,
        behavior=NEUTRAL,
    )
    assert sum(bids.values()) == 20
