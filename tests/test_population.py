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
from leilao.config import Discipline, SimulationConfig
from leilao.grading import draw_grades, grade_for_attempt
from leilao.population import Student, generate_students
from leilao.simulation import run_simulation

GRADE = [
    Discipline("D1", seats=20, hours=60),
    Discipline("D2", seats=20, hours=60),
    Discipline("D3", seats=20, hours=60, prerequisites=("D1",)),
    Discipline("D4", seats=20, hours=60, prerequisites=("D2",)),
]
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


def _grade_config(mean: float, stddev: float, disciplines, **overrides):
    return SimulationConfig(
        disciplines=disciplines,
        grade_mean=mean,
        grade_stddev=stddev,
        # As 40 disciplinas são todas de 1º período: o ingressante cursaria as
        # 40 de uma vez, e a eq. (4) tem de caber.
        max_hours=40 * 60,
        **overrides,
    )


def test_grades_follow_the_normal_of_the_scenario():
    """Muitos sorteios: a média amostral cai perto da média do cenário, e o
    desvio maior de fato espalha mais. O sorteio sai **cru** — sem truncagem e
    sem arredondamento —, porque quem o transforma em nota é `grade_for_attempt`,
    depois de aplicar o deslocamento da recursada."""
    disciplines = [Discipline(f"D{i}", seats=50, hours=60) for i in range(1, 41)]
    students = [Student(id=f"a{i:03d}", name=f"Aluno {i}", credits=10) for i in range(120)]

    def sample(stddev: float) -> list[float]:
        config = _grade_config(6.5, stddev, disciplines, periods=3)
        return list(draw_grades(students, disciplines, config, np.random.default_rng(0)).values())

    tight, wide = sample(0.5), sample(2.0)
    # Uma linha por (aluno, disciplina, período).
    assert len(tight) == 120 * 40 * 3
    for values in (tight, wide):
        assert abs(sum(values) / len(values) - 6.5) < 0.1
    assert np.std(wide) > np.std(tight)
    # Cru: a cauda larga passa dos dois lados do domínio das notas.
    assert min(wide) < 0 and max(wide) > 10
    assert all(0 <= grade_for_attempt(v, 1, 2.5) <= 10 for v in wide)


def test_there_is_one_grade_draw_per_period():
    """A matriz de notas é por período: o mesmo par (aluno, disciplina) sorteia
    de novo a cada semestre, em vez de carregar um valor fixo."""
    disciplines = [Discipline("A", seats=50, hours=60)]
    students = [Student(id="a1", name="Fulano", credits=10)]
    config = _grade_config(6.5, 1.5, disciplines, periods=5)
    grades = draw_grades(students, disciplines, config, np.random.default_rng(1))

    assert set(grades) == {("a1", "A", t) for t in range(1, 6)}
    assert len(set(grades.values())) == 5


def test_a_retake_shifts_the_mean_of_the_draw():
    """eq. (33): a recursada não soma o incremento à nota anterior — ela desloca
    a **média** de onde a nota nova é sorteada. Em distribuição dá no mesmo que
    somar o incremento ao sorteio do período, e é assim que a conta é feita."""
    rng = np.random.default_rng(4)
    draws = rng.normal(5.0, 1.0, size=20000)
    first = [grade_for_attempt(v, 1, 2.0) for v in draws]
    third = [grade_for_attempt(v, 3, 2.0) for v in draws]
    # Duas recursadas sobem a média em 2 x 2,0 — menos o que satura em 10.
    assert np.mean(third) - np.mean(first) == pytest.approx(4.0, abs=0.15)
    # E não é mais monotônico por sorteio: a nota de uma recursada pode sair
    # abaixo da tentativa anterior, porque o sorteio é novo.
    later = [grade_for_attempt(v, 2, 2.0) for v in rng.normal(5.0, 1.0, size=20000)]
    assert any(b < a for a, b in zip(first, later))


def test_a_bigger_learning_gain_recovers_a_failure_faster():
    """O incremento é do cenário: com a mesma nota de partida, quem tem o ganho
    maior volta a passar antes."""

    def first_approval(gain: float) -> list[int]:
        config = SimulationConfig(
            disciplines=[Discipline("A", seats=50, hours=60)],
            periods=6,
            students_per_period=10,
            grade_mean=2.0,
            grade_stddev=0.1,
            learning_gain=gain,
            seed=8,
        )
        attempts = []
        for history in run_simulation(config).histories:
            for record in history.periods:
                hit = next((r for r in record.requests if r.approved), None)
                if hit is not None:
                    attempts.append(hit.attempt)
                    break
        return attempts

    fast, slow = first_approval(3.0), first_approval(0.5)
    assert fast, "com ganho 3,0 alguém deveria aprovar dentro do horizonte"
    mean = lambda values: sum(values) / len(values)  # noqa: E731
    assert not slow or mean(fast) < mean(slow)


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
    entre a maior e a menor utilidade da linha lê isso direto."""
    students = generate_students(make_config(), np.random.default_rng(2))

    def spread(sigma: float) -> float:
        config = make_config(utility_sigma=sigma)
        rows = draw_utilities(students, config, np.random.default_rng(2))
        ratios = [max(row.values()) / min(row.values()) for row in rows.values()]
        return sum(ratios) / len(ratios)

    assert spread(0.25) < spread(1.0) < spread(3.0)
    # Sigma minúsculo é indiferença: a linha converge para 1/|B|.
    flat = draw_utilities(
        students, make_config(utility_sigma=1e-4), np.random.default_rng(2)
    )
    assert all(
        value == pytest.approx(1 / len(GRADE), abs=5e-3)
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
    cairia na primeira faixa, de modo que sigmas diferentes sairiam iguais."""
    config = make_config(utility_sigma=1.0)
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
        at = make_config(utility_sigma=sigma)
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
        disciplines=[Discipline(name, seats=20, hours=60) for name in ("A", "B", "C")],
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
    disciplines = [
        Discipline("A", seats=50, hours=60),
        Discipline("B", seats=50, hours=60),
        *[
            Discipline(name, seats=50, hours=60, prerequisites=("A",))
            for name in ("C", "D", "E", "F", "G")
        ],
    ]

    def loads(max_hours: int) -> list[int]:
        config = SimulationConfig(
            disciplines=disciplines,
            periods=4,
            students_per_period=10,
            grade_mean=9.0,
            grade_stddev=0.5,
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
