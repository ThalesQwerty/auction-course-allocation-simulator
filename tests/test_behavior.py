import numpy as np
import pytest

from disciplines import disciplines_from_predecessors
from leilao.behavior import (
    NEUTRAL,
    Behavior,
    Signals,
    compute_bids,
    decision_scores,
    draw_utilities,
    utility_matrix,
)
from leilao.config import Discipline, SimulationConfig
from leilao.grading import grade_for_attempt
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
    return SimulationConfig(disciplines=disciplines, students_per_period=3, **overrides)


def student(**overrides) -> Student:
    """Um aluno qualquer: o que importa aqui é o conjunto elegível dele. O
    sorteio das duas matrizes é testado em `test_population.py`."""
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
    """Sem pré-requisito não é entrada. A raiz livre entra no conjunto elegível
    de quem não aprovou nada e fica fora da matrícula garantida."""
    config = SimulationConfig(
        disciplines=disciplines_from_predecessors(
            ("Entrada", 5, 60),
            ("Livre", 5, 60, False),
            ("Seguinte", 5, 60, ("Entrada",)),
        ),
        students_per_period=2,
        max_hours=120,
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
            students_per_period=2,
            max_hours=120,
        )


def test_a_scenario_without_entry_disciplines_is_rejected():
    with pytest.raises(ValueError, match="disciplina de entrada"):
        SimulationConfig(
            disciplines=disciplines_from_predecessors(("Livre", 5, 60, False)),
            students_per_period=1,
            max_hours=60,
        )


def test_a_cycle_of_unlocks_is_rejected():
    """Uma cadeia que se fecha não tem altura nem período: as disciplinas dela
    nunca ficariam elegíveis, e o cenário não se conclui por construção."""
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


def test_utilities_respect_height_invariant():
    """s_x > s_y ⇒ u_x > u_y em toda linha sorteada."""
    config = make_config(periods=4)
    students = [student(id=f"a{i}") for i in range(5)]
    rows = draw_utilities(students, config, np.random.default_rng(0))
    heights = config.heights()
    for row in rows.values():
        for x, ux in row.items():
            for y, uy in row.items():
                if heights[x] > heights[y]:
                    assert ux > uy, (x, y, ux, uy, heights[x], heights[y])


def test_utility_matrix_covers_only_the_eligible_disciplines():
    """eq. (42): só entra o que o aluno ainda precisa cursar *e* já pode — a
    bloqueada por pré-requisito vale zero tanto quanto a já aprovada."""
    config = make_config(periods=20)
    novice = student()
    row = draw_utilities([novice], config, np.random.default_rng(3))[("a1", 1)]

    utilities = utility_matrix(row=row, student=novice, config=config)
    # Quem não aprovou nada só alcança o 1º período da grade.
    assert set(utilities) == {"D1", "D2", "D3"}
    # eq. (41): utilidades distintas entre si.
    assert len(set(utilities.values())) == len(utilities)
    # eq. (43): a soma do recorte é o U_a^(t), menor que 1 porque metade da
    # grade está fora do alcance dele — a linha inteira é que vale 1.
    assert 0 < sum(utilities.values()) < 1
    assert sum(row.values()) == pytest.approx(1.0)


def test_approving_a_prerequisite_unlocks_the_next_discipline():
    config = make_config()
    row = draw_utilities([student()], config, np.random.default_rng(1))[("a1", 1)]

    before = utility_matrix(row=row, student=student(), config=config)
    after = utility_matrix(row=row, student=student(grades={"D1": 8.0}), config=config)
    # D1 sai (aprovada) e D4 entra (pré-requisito cumprido); D6 continua fora,
    # porque depende de D4.
    assert set(before) == {"D1", "D2", "D3"}
    assert set(after) == {"D2", "D3", "D4"}


def test_a_failed_prerequisite_does_not_unlock_anything():
    """Cursar não basta: a eq. (42) exige aprovação — n_{a,x} >= n_min."""
    config = make_config()
    row = draw_utilities([student()], config, np.random.default_rng(7))[("a1", 1)]
    failed = student(grades={"D1": 4.9}, attempts={"D1": 1})
    assert set(utility_matrix(row=row, student=failed, config=config)) == {"D1", "D2", "D3"}


def test_utility_matrix_is_a_pure_function_of_the_row():
    """A matriz é parâmetro de entrada: a mesma linha e o mesmo estado do aluno
    têm de dar sempre a mesma utilidade, chamados em qualquer ordem."""
    config = make_config()
    row = draw_utilities([student()], config, np.random.default_rng(5))[("a1", 1)]

    first = utility_matrix(row=row, student=student(), config=config)
    utility_matrix(row=row, student=student(id="a2", grades={"D2": 9.0}), config=config)
    assert utility_matrix(row=row, student=student(), config=config) == first


def test_approving_a_discipline_only_drops_it_from_the_matrix():
    """Aprovar uma disciplina tira ela da matriz e **não mexe nas outras**: sem
    renormalização, o que sobra vale exatamente o que valia. É o que faz a
    preferência do aluno ser a mesma do início ao fim da simulação."""
    config = make_config()
    row = draw_utilities([student()], config, np.random.default_rng(9))[("a1", 1)]

    before = utility_matrix(row=row, student=student(), config=config)
    # D3 aprovada: D1 e D2 continuam elegíveis, e D5 não entra (falta D2).
    after = utility_matrix(row=row, student=student(grades={"D3": 8.0}), config=config)
    assert "D3" in before and "D3" not in after
    assert after["D1"] == before["D1"] and after["D2"] == before["D2"]
    assert sum(after.values()) == pytest.approx(sum(before.values()) - before["D3"])


def test_an_empty_eligible_set_gives_no_utility():
    """Quem aprovou a grade inteira não quer mais nada — e, por isso, já se
    formou antes de chegar a um leilão."""
    config = make_config()
    row = draw_utilities([student()], config, np.random.default_rng(2))[("a1", 1)]
    done = student(grades={name: 9.0 for name in ("D1", "D2", "D3", "D4", "D5", "D6")})
    assert utility_matrix(row=row, student=done, config=config) == {}


def _harmonic_value(bids: dict[str, int], utilities: dict[str, float]) -> float:
    """O que o aluno extrai de uma repartição: c créditos em x valem u_x vezes o
    c-ésimo número harmônico, porque o N-ésimo crédito rende u_x / N."""
    return sum(
        utilities[name] * sum(1.0 / step for step in range(1, credits + 1))
        for name, credits in bids.items()
    )


def _splits(total: int, parts: int):
    """Todas as formas de repartir `total` créditos inteiros entre `parts`
    disciplinas — a busca exaustiva contra a qual o guloso é conferido."""
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in _splits(total - first, parts - 1):
            yield (first, *rest)


def test_bids_spend_the_whole_budget():
    """Não há poupança de créditos: todo crédito a mais tem ganho marginal
    positivo, e o que sobra não passa para o período seguinte."""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    for budget in range(1, 16):
        bids = compute_bids(utilities=utilities, available=list(utilities), budget=budget)
        assert sum(bids.values()) == budget
        # eq. (18): lance nulo não é demanda — quem aparece recebeu crédito.
        assert all(credits > 0 for credits in bids.values())


def test_the_marginal_utility_decays_with_each_extra_credit():
    """O N-ésimo crédito numa disciplina vale u_x / N, e é isso que decide a
    ordem: a preferida só repete quando o que ela ainda rende supera o primeiro
    crédito da seguinte."""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    common = dict(utilities=utilities, available=list(utilities))
    # 1º crédito: compara 0,5 com 0,3 e 0,2 — vai para a preferida.
    assert compute_bids(**common, budget=1) == {"D1": 1}
    # 2º: o segundo crédito de D1 vale 0,25, menos que o primeiro de D2 (0,3).
    assert compute_bids(**common, budget=2) == {"D1": 1, "D2": 1}
    # 3º: agora 0,25 ganha do primeiro de D3 (0,2), e D1 repete.
    assert compute_bids(**common, budget=3) == {"D1": 2, "D2": 1}
    assert compute_bids(**common, budget=4) == {"D1": 2, "D2": 1, "D3": 1}


def test_a_large_budget_still_reaches_the_least_preferred_discipline():
    """O decaimento é o que impede o aluno de despejar tudo na preferida: com
    orçamento folgado, até a de menor utilidade recebe crédito."""
    utilities = {"D1": 0.7, "D2": 0.2, "D3": 0.1}
    bids = compute_bids(utilities=utilities, available=list(utilities), budget=20)
    assert set(bids) == {"D1", "D2", "D3"}
    assert bids["D1"] > bids["D2"] > bids["D3"]


def test_the_greedy_split_matches_an_exhaustive_search():
    """O guloso é ótimo porque os pesos são unitários e o ganho marginal cai
    dentro de cada disciplina. Conferido contra todas as repartições possíveis
    do orçamento."""
    utilities = {"D1": 0.44, "D2": 0.31, "D3": 0.17, "D4": 0.08}
    names = list(utilities)
    for budget in range(1, 10):
        bids = compute_bids(utilities=utilities, available=names, budget=budget)
        best = max(
            _harmonic_value(dict(zip(names, split)), utilities)
            for split in _splits(budget, len(names))
        )
        assert _harmonic_value(bids, utilities) == pytest.approx(best)


def test_a_tie_goes_to_the_discipline_listed_first():
    """Empate de utilidade é resolvido pela ordem global de desempate: a ordem
    em que o cenário lista as disciplinas, que é a da interface."""
    tied = {"D1": 0.25, "D2": 0.25, "D3": 0.25, "D4": 0.25}
    # Com 2 créditos e 4 disciplinas idênticas, levam as duas primeiras.
    assert compute_bids(utilities=tied, available=list(tied), budget=2) == {
        "D1": 1,
        "D2": 1,
    }
    # A ordem que decide é a da matriz, não a alfabética nem a de `available`.
    reversed_grade = {name: 0.25 for name in ("D4", "D3", "D2", "D1")}
    assert compute_bids(
        utilities=reversed_grade, available=["D1", "D2", "D3", "D4"], budget=2
    ) == {"D4": 1, "D3": 1}


def test_available_may_arrive_in_any_order():
    """`available` é um filtro, não uma ordenação: embaralhá-lo não muda lance
    nenhum, nem no empate."""
    tied = {"D1": 0.25, "D2": 0.25, "D3": 0.25, "D4": 0.25}
    straight = compute_bids(utilities=tied, available=["D1", "D2", "D3", "D4"], budget=3)
    shuffled = compute_bids(utilities=tied, available=["D3", "D1", "D4", "D2"], budget=3)
    assert straight == shuffled == {"D1": 1, "D2": 1, "D3": 1}


def test_a_tie_between_marginal_gains_also_follows_the_grade_order():
    """O empate pode surgir entre utilidades diferentes: o 2º crédito de uma
    disciplina de utilidade 0,4 rende o mesmo que o 1º de uma de 0,2. Vale a
    mesma ordem."""
    utilities = {"D1": 0.4, "D2": 0.2}
    # 1º crédito: 0,4 em D1. 2º: 0,4/2 = 0,2 empata com 0,2 de D2 — D1 vem antes.
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
    """A mochila côncava compara só razões entre utilidades — u_x/N contra
    u_y/M —, então multiplicar a matriz inteira por uma constante não muda
    lance nenhum."""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    scaled = {name: value * 7 for name, value in utilities.items()}
    common = dict(available=list(utilities), budget=20)
    assert compute_bids(utilities=utilities, **common) == compute_bids(
        utilities=scaled, **common
    )


def test_the_retake_lowers_the_demand_of_the_discipline():
    """A recursada não soma incremento à nota: ela divide a demanda por `t`.
    Com D = 1, a segunda tentativa é tão fácil quanto uma disciplina de
    dificuldade 1/2 seria de primeira."""
    def grade(attempt, difficulty=1.0):
        return grade_for_attempt(
            aptitude=0.5,
            difficulty=difficulty,
            relative_utility=1.0,
            attempt=attempt,
            utility_gain=0.0,
            retake_gain=1.0,
        )

    assert grade(1) < grade(2) < grade(3)
    assert grade(2) == grade(1, difficulty=0.5)
    with pytest.raises(ValueError):
        grade(0)

def test_a_utility_row_sums_to_one_over_the_whole_curriculum():
    """A linha inteira vale 1, e é essa invariante que `metrics.satisfaction`
    usa para dispensar a divisão: com o denominador da eq. (51) fixo em 1, psi
    é a soma simples das utilidades atendidas. Se a normalização mudar, é aqui
    que se descobre — antes de psi passar a mentir."""
    config = make_config()
    rng = np.random.default_rng(config.seed)
    students = generate_students(config, rng)
    rows = draw_utilities(students, config, rng)
    assert rows, "nenhuma linha sorteada"
    for row in rows.values():
        assert set(row) == {d.name for d in config.disciplines}
        assert sum(row.values()) == pytest.approx(1.0)


# --- os genes de comportamento --------------------------------------------


def test_the_neutral_behavior_reproduces_the_model_without_genes():
    """β = 1, ρ = 0, r = 0 têm de dar exatamente o que o modelo dava antes de
    haver comportamento — é a regressão que garante que acrescentar os genes
    não mudou nada por acidente. Hoje **toda a população roda no neutro**."""
    utilities = {"D1": 0.4, "D2": 0.3, "D3": 0.2, "D4": 0.1}
    pool = list(utilities)
    assert compute_bids(
        utilities=utilities, available=pool, budget=10
    ) == compute_bids(
        utilities=utilities, available=pool, budget=10, behavior=NEUTRAL
    )
    # E o score neutro é proporcional à utilidade: a mochila decide igual.
    scores = decision_scores(utilities=utilities, catalogue=len(utilities))
    ratios = [scores[n] / utilities[n] for n in utilities]
    assert max(ratios) == pytest.approx(min(ratios))


def test_the_concentration_gene_moves_the_budget_to_the_favourite():
    """β é o viés de satisfação: grande concentra, e β → 0 achata a mensagem
    até ela virar um conjunto — que é exatamente o que o CR envia."""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    pool = list(utilities)

    def bids(beta):
        return compute_bids(
            utilities=utilities,
            available=pool,
            budget=20,
            behavior=Behavior(concentration=beta),
        )

    assert bids(3.0)["D1"] > bids(1.0)["D1"] > bids(0.2)["D1"]
    # Achatado, os três recebem quase o mesmo.
    flat = bids(0.05)
    assert max(flat.values()) - min(flat.values()) <= 1


def test_the_reserve_gene_stops_the_spending():
    """A reserva corta no ganho marginal, e numa regra só decide quais entram,
    quantos créditos cada uma recebe e quanto se gasta no total: o orçamento
    vira teto, não meta."""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    pool = list(utilities)
    full = compute_bids(utilities=utilities, available=pool, budget=20)
    assert sum(full.values()) == 20  # neutro gasta tudo

    thrifty = compute_bids(
        utilities=utilities, available=pool, budget=20, behavior=Behavior(reserve=1.0)
    )
    assert sum(thrifty.values()) < 20  # sobra crédito
    assert set(thrifty) <= set(full)  # e ele pede menos disciplinas, nunca mais


def test_the_progress_gene_reads_the_published_signals():
    """ρ pesa o avanço esperado — `P(obter)·P(aprovar)·carga·(1+alcance)`. Com
    ρ = 0 os sinais são ignorados; com ρ > 0, duas disciplinas de utilidade
    igual se separam pelo que a universidade publicou."""
    utilities = {"D1": 0.5, "D2": 0.5}
    signals = Signals(
        win={"D1": 0.2, "D2": 1.0},  # D1 é disputada
        pass_rate={"D1": 1.0, "D2": 1.0},
        hours={"D1": 60, "D2": 60},
        reach={"D1": 0, "D2": 0},
    )
    neutral = decision_scores(utilities=utilities, signals=signals, catalogue=2)
    assert neutral["D1"] == pytest.approx(neutral["D2"])

    aware = decision_scores(
        utilities=utilities,
        behavior=Behavior(progress=1.0),
        signals=signals,
        catalogue=2,
    )
    assert aware["D2"] > aware["D1"]  # foge do congestionamento
