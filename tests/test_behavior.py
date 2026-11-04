import numpy as np
import pytest

from disciplines import disciplines_from_predecessors
from leilao.behavior import (
    NEUTRAL,
    Behavior,
    Signals,
    compute_bids,
    decision_scores,
    draw_interest,
    utility_matrix,
)
from leilao.config import Discipline, SimulationConfig
from leilao.equations import attempt_rates
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


def test_the_drawn_row_is_taste_alone_and_sums_to_one():
    """A invariante de altura saiu: a posição na grade **não** ordena mais o
    interesse. O valor curricular entra depois, quando `utility` converte o
    interesse em utilidade, e não dentro do gosto."""
    config = make_config(periods=4)
    students = [student(id=f"a{i}") for i in range(5)]
    rows = draw_interest(students, config, np.random.default_rng(0))
    heights = config.heights()

    assert all(sum(row.values()) == pytest.approx(1.0) for row in rows.values())
    # Alguma linha tem de inverter a ordem por altura — se nenhuma invertesse,
    # a invariante ainda estaria lá disfarçada.
    inverted = any(
        row[x] < row[y]
        for row in rows.values()
        for x, y in [(a, b) for a in row for b in row if heights[a] > heights[b]]
    )
    assert inverted


def test_utility_matrix_covers_only_the_eligible_disciplines():
    """eq. (42): só entra o que o aluno ainda precisa cursar *e* já pode — a
    bloqueada por pré-requisito vale zero tanto quanto a já aprovada."""
    config = make_config(periods=20)
    novice = student()
    row = draw_interest([novice], config, np.random.default_rng(3))[("a1", 1)]

    utilities = utility_matrix(interest=row, student=novice, config=config)
    # Quem não aprovou nada só alcança o 1º período da grade.
    assert set(utilities) == {"D1", "D2", "D3"}
    assert len(set(utilities.values())) == len(utilities)
    # A redistribuição conserva a massa: o que estava fora do alcance desceu
    # para quem o destrava, então o recorte soma o mesmo que a linha inteira.
    # É isso que põe `alpha_u` na mesma unidade da utilidade.
    assert sum(utilities.values()) == pytest.approx(1.0)
    assert sum(row.values()) == pytest.approx(1.0)


def test_approving_a_prerequisite_unlocks_the_next_discipline():
    config = make_config()
    row = draw_interest([student()], config, np.random.default_rng(1))[("a1", 1)]

    before = utility_matrix(interest=row, student=student(), config=config)
    after = utility_matrix(interest=row, student=student(grades={"D1": 8.0}), config=config)
    # D1 sai (aprovada) e D4 entra (pré-requisito cumprido); D6 continua fora,
    # porque depende de D4.
    assert set(before) == {"D1", "D2", "D3"}
    assert set(after) == {"D2", "D3", "D4"}


def test_a_failed_prerequisite_does_not_unlock_anything():
    """Cursar não basta: a eq. (42) exige aprovação — n_{a,x} >= n_min."""
    config = make_config()
    row = draw_interest([student()], config, np.random.default_rng(7))[("a1", 1)]
    failed = student(grades={"D1": 4.9}, attempts={"D1": 1})
    assert set(utility_matrix(interest=row, student=failed, config=config)) == {"D1", "D2", "D3"}


def test_utility_matrix_is_a_pure_function_of_the_row():
    """A matriz é parâmetro de entrada: a mesma linha e o mesmo estado do aluno
    têm de dar sempre a mesma utilidade, chamados em qualquer ordem."""
    config = make_config()
    row = draw_interest([student()], config, np.random.default_rng(5))[("a1", 1)]

    first = utility_matrix(interest=row, student=student(), config=config)
    utility_matrix(interest=row, student=student(id="a2", grades={"D2": 9.0}), config=config)
    assert utility_matrix(interest=row, student=student(), config=config) == first


def test_approving_a_discipline_spreads_its_utility_over_what_is_left():
    """Aprovar tira a disciplina da matriz e **distribui a utilidade dela
    igualmente entre as elegíveis** — é o que impede o veterano de ficar com
    pouca massa e perder todo leilão. A massa total não se mexe."""
    config = make_config()
    row = draw_interest([student()], config, np.random.default_rng(9))[("a1", 1)]

    before = utility_matrix(interest=row, student=student(), config=config)
    # D3 aprovada: D1 e D2 continuam elegíveis, e D5 não entra (falta D2).
    after = utility_matrix(interest=row, student=student(grades={"D3": 8.0}), config=config)
    assert "D3" in before and "D3" not in after
    assert sum(after.values()) == pytest.approx(sum(before.values()))
    # D1 recebe exatamente metade de D3, que é a divisão igual entre as duas
    # elegíveis. D2 recebe essa metade e mais a parte de D5 que D3 segurava.
    assert after["D1"] - before["D1"] == pytest.approx(row["D3"] / 2)


def test_an_empty_eligible_set_gives_no_utility():
    """Quem aprovou a grade inteira não quer mais nada — e, por isso, já se
    formou antes de chegar a um leilão."""
    config = make_config()
    row = draw_interest([student()], config, np.random.default_rng(2))[("a1", 1)]
    done = student(grades={name: 9.0 for name in ("D1", "D2", "D3", "D4", "D5", "D6")})
    assert utility_matrix(interest=row, student=done, config=config) == {}


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
    """A recursada entra nos mesmos dois expoentes que a dificuldade, do outro
    lado da razão. Com D = 1, a segunda tentativa é tão fácil quanto uma
    disciplina de dificuldade 1/2 seria de primeira — e é por isso que não há
    botão de ganho por recursada: quem calibra isso é a dificuldade."""
    def rates(attempt, difficulty=1.0):
        return attempt_rates(
            zero_rate=0.05,
            max_rate=0.05,
            difficulty=difficulty,
            attempt=attempt,
        )

    # Recursar derruba a chance de zerar e levanta a de tirar 10.
    assert rates(1)[0] > rates(2)[0] > rates(3)[0]
    assert rates(1)[1] < rates(2)[1] < rates(3)[1]
    assert rates(2) == rates(1, difficulty=0.5)
    with pytest.raises(ValueError):
        rates(0)


def test_a_utility_row_sums_to_one_over_the_whole_curriculum():
    """A linha inteira vale 1, e é essa invariante que `metrics.satisfaction`
    usa para dispensar a divisão: com o denominador da eq. (51) fixo em 1, psi
    é a soma simples das utilidades atendidas. Se a normalização mudar, é aqui
    que se descobre — antes de psi passar a mentir."""
    config = make_config()
    rng = np.random.default_rng(config.seed)
    students = generate_students(config, rng)
    rows = draw_interest(students, config, rng)
    assert rows, "nenhuma linha sorteada"
    for row in rows.values():
        assert set(row) == {d.name for d in config.disciplines}
        assert sum(row.values()) == pytest.approx(1.0)


# --- os genes de comportamento --------------------------------------------


def test_the_baseline_genome_asks_in_proportion_to_utility():
    """β_u = 1 com os outros dois em 0 é a linha de base: o score **é** a
    utilidade, e as duas mochilas decidem o que decidiriam sem genoma."""
    utilities = {"D1": 0.4, "D2": 0.3, "D3": 0.2, "D4": 0.1}
    pool = list(utilities)
    assert compute_bids(
        utilities=utilities, available=pool, budget=10
    ) == compute_bids(
        utilities=utilities, available=pool, budget=10, behavior=NEUTRAL
    )
    scores = decision_scores(utilities=utilities)
    ratios = [scores[n] / utilities[n] for n in utilities]
    assert max(ratios) == pytest.approx(min(ratios))


def test_a_gene_at_zero_ignores_its_signal():
    """A leitura comum aos quatro: 0 quer dizer "ignora esse sinal", porque
    x⁰ = 1 para todos."""
    utilities = {"D1": 0.6, "D2": 0.4}
    signals = Signals(supply={"D1": 0.1, "D2": 0.9}, approval={"D1": 0.2, "D2": 0.8})

    assert decision_scores(
        utilities=utilities, behavior=Behavior(beta_u=1.0), signals=signals
    ) == decision_scores(utilities=utilities, behavior=Behavior(beta_u=1.0))

    # β_u = 0 achata a própria preferência: os dois scores ficam iguais.
    flat = decision_scores(utilities=utilities, behavior=Behavior(beta_u=0.0))
    assert flat["D1"] == pytest.approx(flat["D2"])


def test_the_utility_gene_concentrates_and_inverts():
    """β_u é expoente: acima de 1 concentra nas mais úteis, abaixo de 0
    inverte e concentra nas menos úteis."""
    utilities = {"D1": 0.5, "D2": 0.3, "D3": 0.2}
    pool = list(utilities)

    def bids(beta_u):
        return compute_bids(
            utilities=utilities,
            available=pool,
            budget=20,
            behavior=Behavior(beta_u=beta_u),
        )

    assert bids(3.0)["D1"] > bids(1.0)["D1"] > bids(0.2)["D1"]
    flat = bids(0.0)
    assert max(flat.values()) - min(flat.values()) <= 1
    # Expoente negativo põe o orçamento na que ele menos quer.
    inverted = bids(-2.0)
    assert inverted["D3"] > inverted["D1"]


def test_the_reserve_gene_cuts_the_choice_set():
    """`alpha_u` está na mesma unidade da utilidade: com elegíveis
    valendo 0,6 e 0,4 e reserva 0,5, só a primeira entra. O orçamento
    continua indo inteiro para o que foi admitido."""
    utilities = {"D1": 0.6, "D2": 0.4}
    pool = list(utilities)

    full = compute_bids(utilities=utilities, available=pool, budget=20)
    assert set(full) == {"D1", "D2"}
    assert sum(full.values()) == 20

    picky = compute_bids(
        utilities=utilities, available=pool, budget=20, behavior=Behavior(alpha_u=0.5)
    )
    assert set(picky) == {"D1"}
    assert sum(picky.values()) == 20


def test_the_published_signals_separate_equal_utilities():
    """β_v e β_n pesam o que a universidade publicou. Com utilidade igual,
    duas disciplinas só se separam pelos índices — e o sinal do gene diz para
    que lado."""
    utilities = {"D1": 0.5, "D2": 0.5}
    # D1 é disputada e reprova mais; D2 é folgada e aprova mais.
    signals = Signals(
        supply={"D1": 0.1, "D2": 0.9}, approval={"D1": 0.3, "D2": 0.8}
    )

    neutral = decision_scores(utilities=utilities, signals=signals)
    assert neutral["D1"] == pytest.approx(neutral["D2"])

    averse = decision_scores(
        utilities=utilities, behavior=Behavior(beta_v=1.0), signals=signals
    )
    assert averse["D2"] > averse["D1"]

    # Negativo caça vaga escassa — o mesmo gene, o outro lado.
    seeker = decision_scores(
        utilities=utilities, behavior=Behavior(beta_v=-1.0), signals=signals
    )
    assert seeker["D1"] > seeker["D2"]

    easy = decision_scores(
        utilities=utilities, behavior=Behavior(beta_n=1.0), signals=signals
    )
    assert easy["D2"] > easy["D1"]
