"""A população e as duas matrizes sorteadas na inicialização.

Não há perfis de aluno: toda a população sai das mesmas duas normais do cenário
— a das notas e a das utilidades —, e o que distingue um aluno do outro é só o
que a seed sorteou para ele. Aqui se testa que as duas matrizes têm a forma que
o modelo diz que têm, e que o que o cenário promete (W_a, incremento de
aprendizado) de fato morde.
"""
import numpy as np
import pytest

from leilao.behavior import (
    DISTRIBUTION_BINS,
    UNDERFLOW_GUARD,
    draw_utilities,
    utility_distribution,
    utility_matrix,
)
from disciplines import disciplines_from_predecessors
from leilao.config import Discipline, SimulationConfig
from leilao.grading import draw_aptitudes, draw_grade_noise, grade_for_attempt
from leilao.population import Student, generate_students
from leilao.simulation import run_simulation

GRADE = disciplines_from_predecessors(
    ("D1", 20, 60),
    ("D2", 20, 60),
    ("D3", 20, 60, ("D1",)),
    ("D4", 20, 60, ("D2",)),
)
# W_a: a grade tem 4 disciplinas de 60 h, 2 por período.
WORKLOAD = 180


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=5,
        students_per_period=8,
        max_hours=WORKLOAD,
        seed=7,
    )
    return SimulationConfig(**{**base, **overrides})


# --- a matriz de notas -----------------------------------------------------


def _grade_config(disciplines, **overrides):
    return SimulationConfig(
        disciplines=disciplines,
        # As 40 disciplinas são todas de entrada: o ingressante cursaria as 40
        # de uma vez, e a eq. (4) tem de caber.
        max_hours=40 * 60,
        **overrides,
    )


def test_aptitude_is_drawn_once_per_pair_and_persists():
    """A aptidão é **traço**: um sorteio por (aluno, disciplina), sem dimensão
    de período. O que varia por período é o choque, não ela."""
    disciplines = [Discipline(f"D{i}", seats=50, hours=60, entry=True) for i in range(1, 41)]
    students = [Student(id=f"a{i:03d}", name=f"Aluno {i}", credits=10) for i in range(120)]
    config = _grade_config(disciplines, periods=3)

    aptitudes = draw_aptitudes(students, disciplines, config, np.random.default_rng(0))
    assert len(aptitudes) == 120 * 40
    assert all(0.0 < a < 1.0 for a in aptitudes.values())
    # Beta(4, 2) tem média 4/6.
    assert abs(sum(aptitudes.values()) / len(aptitudes) - 4 / 6) < 0.01

    noise = draw_grade_noise(students, disciplines, config, np.random.default_rng(0))
    assert len(noise) == 120 * 40 * 3  # este sim é por período


def test_the_grade_is_the_aptitude_when_the_demand_is_standard():
    """Com dificuldade 1, primeira tentativa, sem acoplamento e sem ruído, o
    expoente é 1 e a nota **é** a aptidão. É o que lhe dá leitura direta."""
    for aptitude in (0.2, 0.55, 0.86, 0.99):
        assert grade_for_attempt(
            aptitude=aptitude,
            difficulty=1.0,
            relative_utility=1.0,
            attempt=1,
            coupling=0.0,
            noise=0.0,
            noise_sigma=0.0,
        ) == round(100 * aptitude) / 10


def test_difficulty_and_attempt_enter_as_a_ratio():
    """D e t entram como D/t: dificuldade 2 na **segunda** tentativa equivale a
    dificuldade 1 na primeira. É o que faz a dificuldade se ler em tentativas."""
    def grade(difficulty, attempt):
        return grade_for_attempt(
            aptitude=0.7,
            difficulty=difficulty,
            relative_utility=1.0,
            attempt=attempt,
            coupling=0.0,
            noise=0.0,
            noise_sigma=0.0,
        )

    assert grade(1.0, 1) == grade(2.0, 2) == grade(3.0, 3)
    # E não é "dificuldade 2 ≡ dificuldade 1 na segunda tentativa".
    assert grade(2.0, 1) != grade(1.0, 2)
    # Mais difícil derruba; recursar levanta.
    assert grade(2.0, 1) < grade(1.0, 1) < grade(1.0, 2)


def test_the_interest_coupling_is_off_by_default():
    """Com w = 0 a utilidade some da fórmula — é o controle que deixa a função
    de nota neutra entre os mecanismos."""
    def grade(u_rel, coupling):
        return grade_for_attempt(
            aptitude=0.7,
            difficulty=1.0,
            relative_utility=u_rel,
            attempt=1,
            coupling=coupling,
            noise=0.0,
            noise_sigma=0.0,
        )

    assert grade(0.1, 0.0) == grade(1.0, 0.0) == grade(5.0, 0.0)
    # Ligado, querer mais rende mais, e querer pouco é quase reprovação certa.
    assert grade(0.3, 1.0) < grade(1.0, 1.0) < grade(3.0, 1.0)


def test_a_retake_no_longer_guarantees_a_higher_grade():
    """O choque por tentativa é o que devolve sorte à recursada. Sem ele a nota
    seria exata e recursar sempre melhoraria — revertendo uma decisão do
    modelo — e a variância das notas passaria a vir do resorteio da utilidade,
    amarrando a nota ao parâmetro de estabilidade da preferência."""
    rng = np.random.default_rng(4)
    first, second = [], []
    for _ in range(20000):
        kwargs = dict(
            aptitude=0.6, difficulty=1.0, relative_utility=1.0,
            coupling=0.0, noise_sigma=0.3,
        )
        first.append(grade_for_attempt(attempt=1, noise=rng.normal(), **kwargs))
        second.append(grade_for_attempt(attempt=2, noise=rng.normal(), **kwargs))
    # Em média a recursada melhora...
    assert np.mean(second) > np.mean(first)
    # ...mas não em cada sorteio.
    assert any(b < a for a, b in zip(first, second))


def test_the_grade_stays_on_the_scale_and_reaches_the_top():
    """Limitada por construção, sem truncagem: `a^E` nunca sai de (0, 1). E o
    arredondamento é `round`, não `floor` — com `floor` o teto seria 9,9."""
    grades = [
        grade_for_attempt(
            aptitude=a, difficulty=d, relative_utility=1.0, attempt=1,
            coupling=0.0, noise=0.0, noise_sigma=0.0,
        )
        for a in (0.01, 0.3, 0.7, 0.999)
        for d in (0.5, 1.0, 4.0)
    ]
    assert all(0.0 <= g <= 10.0 for g in grades)
    assert max(grades) == 10.0


# --- a matriz de utilidades ------------------------------------------------


def test_the_drawn_row_sums_to_one_over_the_whole_grade():
    """Passo 3 da construção: a linha é dividida pelo somatório, então vale 1
    sobre a grade inteira — antes de qualquer recorte por elegibilidade."""
    config = make_config()
    students = generate_students(config, np.random.default_rng(3))
    rows = draw_utilities(students, config, np.random.default_rng(3))

    # Uma linha por (aluno, período).
    assert set(rows) == {
        (s.id, period) for s in students for period in range(1, config.periods + 1)
    }
    for row in rows.values():
        assert set(row) == {d.name for d in GRADE}
        assert sum(row.values()) == pytest.approx(1.0)
        assert all(value >= 0 for value in row.values())
        # eq. (41): contínuas, portanto distintas entre si.
        assert len(set(row.values())) == len(row)


def test_a_wider_sigma_makes_the_student_differentiate_more():
    """É o que sigma existe para controlar, e o papel que o expoente de afinidade
    tinha antes dos perfis saírem: **grande concentra, pequeno achata**. A razão
    entre a maior e a menor utilidade da linha lê isso direto.

    A grade é plana (altura 0 em todas): entre camadas a invariante de altura
    já ordena a linha, e o sigma só manda *dentro* da mesma altura."""
    flat_grade = [
        Discipline("A", seats=20, hours=60, entry=True),
        Discipline("B", seats=20, hours=60, entry=True),
        Discipline("C", seats=20, hours=60, entry=True),
        Discipline("D", seats=20, hours=60, entry=True),
    ]
    # W_a precisa caber as quatro de uma vez — são todas de 1º período.
    flat_kw = dict(disciplines=flat_grade, max_hours=240)
    students = generate_students(make_config(**flat_kw), np.random.default_rng(2))

    def spread(sigma: float) -> float:
        config = make_config(**flat_kw, utility_sigma=sigma)
        rows = draw_utilities(students, config, np.random.default_rng(2))
        ratios = [max(row.values()) / min(row.values()) for row in rows.values()]
        return sum(ratios) / len(ratios)

    assert spread(0.25) < spread(1.0) < spread(3.0)
    # Sigma minúsculo é indiferença: a linha converge para 1/|B|.
    flat = draw_utilities(
        students,
        make_config(**flat_kw, utility_sigma=1e-4),
        np.random.default_rng(2),
    )
    assert all(
        value == pytest.approx(1 / len(flat_grade), abs=5e-3)
        for row in flat.values()
        for value in row.values()
    )


def test_the_draw_is_always_positive():
    """A log-normal só chegaria a zero com expoente abaixo de -745, o que não
    acontece em sigma nenhum que faça sentido — mas a invariante importa: zero
    marca o **inelegível**, e as duas mochilas filtram por `utilidade > 0`. Uma
    utilidade nula tiraria a disciplina do conjunto de escolha e o aluno nunca a
    cursaria, nem quando fosse a única disponível."""
    for sigma in (0.1, 1.0, 10.0):
        config = make_config(utility_sigma=sigma)
        students = generate_students(config, np.random.default_rng(11))
        rows = draw_utilities(students, config, np.random.default_rng(11))
        assert rows
        for row in rows.values():
            assert min(row.values()) > 0
            assert sum(row.values()) == pytest.approx(1.0)


def test_the_guard_never_fires_in_practice():
    """A guarda é insurance, não mecanismo: em sigma nenhum razoável ela encosta
    no sorteio. (A Gamma que havia antes precisava dela de verdade, e por isso a
    faixa de parâmetro utilizável era limitada.)"""
    config = make_config(utility_sigma=3.0)
    students = generate_students(config, np.random.default_rng(12))
    for row in draw_utilities(students, config, np.random.default_rng(12)).values():
        assert all(value > UNDERFLOW_GUARD for value in row.values())


def test_the_distribution_histogram_describes_one_students_row():
    """O histograma reescala **cada linha** ao próprio [mínimo, máximo]. Global
    degeneraria: um único extremo da matriz definiria o intervalo e quase tudo
    cairia na primeira faixa, de modo que sigmas diferentes sairiam iguais.

    Grade plana: a invariante de altura não cria extremos estruturais que
    mascarem o efeito do sigma no histograma."""
    flat_grade = [
        Discipline("A", seats=20, hours=60, entry=True),
        Discipline("B", seats=20, hours=60, entry=True),
        Discipline("C", seats=20, hours=60, entry=True),
        Discipline("D", seats=20, hours=60, entry=True),
    ]
    flat_kw = dict(disciplines=flat_grade, max_hours=240)
    config = make_config(**flat_kw, utility_sigma=1.0)
    students = generate_students(config, np.random.default_rng(13))
    rows = draw_utilities(students, config, np.random.default_rng(13))

    fractions = utility_distribution(rows)
    assert len(fractions) == DISTRIBUTION_BINS
    assert sum(fractions) == pytest.approx(1.0)
    assert all(value >= 0 for value in fractions)
    # A última faixa guarda o máximo de cada linha, então nunca é vazia.
    assert fractions[-1] > 0

    # Sigma maior concentra: mais massa na primeira faixa, porque o máximo da
    # linha se afasta do resto.
    def first_bin(sigma: float) -> float:
        at = make_config(**flat_kw, utility_sigma=sigma)
        return utility_distribution(
            draw_utilities(generate_students(at, np.random.default_rng(13)), at, np.random.default_rng(13))
        )[0]

    assert first_bin(0.25) < first_bin(1.0) < first_bin(3.0)


def test_only_the_zeros_change_between_periods():
    """O cerne do modelo: a linha é uma só para a simulação inteira. O que muda
    de um período para o outro é quem está no conjunto elegível, nunca o valor
    de quem está."""
    config = make_config()
    students = generate_students(config, np.random.default_rng(4))
    row = draw_utilities(students, config, np.random.default_rng(4))[(students[0].id, 1)]

    novice = Student(id="x", name="X", credits=10)
    veteran = Student(id="x", name="X", credits=10, grades={"D1": 9.0})
    first = utility_matrix(row=row, student=novice, config=config)
    second = utility_matrix(row=row, student=veteran, config=config)

    # D1 sai (aprovada) e D3 entra (pré-requisito cumprido); D4 continua fora,
    # porque depende de D2.
    assert set(first) == {"D1", "D2"}
    assert set(second) == {"D2", "D3"}
    # O que sobrevive aos dois recortes vale exatamente o mesmo, e o mesmo que
    # na linha sorteada: nada é renormalizado.
    assert first["D2"] == second["D2"] == row["D2"]


def test_the_eligible_sum_is_the_period_utility():
    """Sem renormalização, a soma do recorte é o U_a^(t) da eq. (43): 1 só
    quando a grade inteira é elegível, menor sempre que algo está fora."""
    config = make_config()
    students = generate_students(config, np.random.default_rng(6))
    row = draw_utilities(students, config, np.random.default_rng(6))[(students[0].id, 1)]

    novice = Student(id="x", name="X", credits=10)
    partial = sum(utility_matrix(row=row, student=novice, config=config).values())
    assert 0 < partial < 1

    # Numa grade sem pré-requisito nenhum, tudo é elegível de saída e a soma é 1.
    flat = SimulationConfig(
        disciplines=[Discipline(name, seats=20, hours=60, entry=True) for name in ("A", "B", "C")],
        students_per_period=8,
        max_hours=WORKLOAD,
    )
    flat_row = draw_utilities(
        generate_students(flat, np.random.default_rng(6)), flat, np.random.default_rng(6)
    )[("a00000", 1)]
    whole = utility_matrix(row=flat_row, student=Student("x", "X", 10), config=flat)
    assert sum(whole.values()) == pytest.approx(1.0)


# --- o que o cenário promete ------------------------------------------------


def test_the_workload_cap_bounds_the_enrolled_hours():
    """W_a é do cenário e morde onde há mais elegíveis do que ele comporta: duas
    disciplinas de 1º período e cinco atrás de uma delas, de modo que no 2º
    período sobram 300 h elegíveis."""
    disciplines = disciplines_from_predecessors(
        ("A", 50, 60),
        ("B", 50, 60),
        ("C", 50, 60, ("A",)),
        ("D", 50, 60, ("A",)),
        ("E", 50, 60, ("A",)),
        ("F", 50, 60, ("A",)),
        ("G", 50, 60, ("A",)),
    )

    def loads(max_hours: int) -> list[int]:
        config = SimulationConfig(
            disciplines=disciplines,
            periods=4,
            students_per_period=10,
            max_hours=max_hours,
            seed=5,
        )
        result = run_simulation(config)
        return [r.enrolled_hours for h in result.histories for r in h.periods]

    tight, roomy = loads(120), loads(300)
    assert max(tight) <= 120
    assert max(roomy) <= 300
    # O teto folgado de fato é usado: alguém carrega mais do que o apertado
    # jamais poderia.
    assert max(roomy) > 120


# --- o recorte do relatório -------------------------------------------------


def test_the_cohort_axis_partitions_the_university():
    """O recorte fatia a mesma população do agregado: somá-lo reproduz
    `overall`, em toda rodada e todo período."""
    result = run_simulation(make_config(periods=6, entry_periods=3))
    reports = [r for p in result.periods for r in (*p.rounds, p.aggregate)]
    assert reports

    for report in reports:
        axis = report.by_cohort
        assert sum(g.active for g in axis) == report.overall.active
        assert sum(g.population for g in axis) == report.overall.population
        assert sum(g.graduated for g in axis) == report.overall.graduated
        keys = [g.group for g in axis]
        assert len(set(keys)) == len(keys)
        assert all(key is not None for key in keys)


def test_every_generation_has_the_same_size():
    """As gerações entram em períodos consecutivos, todas do mesmo tamanho — o
    ingresso não vem da seed."""
    config = make_config(periods=6, entry_periods=3)
    students = generate_students(config, np.random.default_rng(0))
    assert len(students) == 24
    sizes = {entry: 0 for entry in (1, 2, 3)}
    for student in students:
        sizes[student.entry_period] += 1
    assert sizes == {1: 8, 2: 8, 3: 8}
