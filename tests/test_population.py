"""A população e as duas matrizes sorteadas na inicialização."""
import numpy as np
import pytest

from leilao.behavior import (
    DISTRIBUTION_BINS,
    UNDERFLOW_GUARD,
    draw_interest,
    interest_distribution,
    utility_matrix,
)
from profiles import single_axis
from disciplines import disciplines_from_predecessors
from leilao.config import (
    Discipline,
    SimulationConfig,
)
from leilao.equations import (
    attempt_approval,
    grade_mean,
)
from leilao.grading import GradeMeans, draw_grade_quantiles, grade_for_attempt
from leilao.population import Student, generate_students
from leilao.simulation import run_simulation

GRADE = disciplines_from_predecessors(
    ("D1", 20, 60),
    ("D2", 20, 60),
    ("D3", 20, 60, ("D1",)),
    ("D4", 20, 60, ("D2",)),
)
WORKLOAD = 180


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=5,
        students_per_entry_class=8,
        max_hours=WORKLOAD,
        **single_axis(WORKLOAD),
        seed=7,
    )
    return SimulationConfig(**{**base, **overrides})


def _grade_config(disciplines, **overrides):
    return SimulationConfig(
        disciplines=disciplines,
        max_hours=40 * 60,
        slots=40,
        **single_axis(40 * 60),
        **overrides,
    )


def test_the_grade_stays_on_the_scale_and_reaches_both_ends():
    """O latente é ilimitado; o que limita é o instrumento. Arredondar em"""
    shape = {"grade_mean": 6.0, "grade_sd": 2.5}
    grades = [
        grade_for_attempt(quantile=q / 20_000, **shape) for q in range(1, 20_000)
    ]
    assert all(0.0 <= g <= 10.0 for g in grades)
    assert min(grades) == 0.0
    assert max(grades) == 10.0


def test_the_approval_rate_survives_the_clipping():
    """Parametrizar pela aprovação é o que faz o número sobreviver ao clipe:"""
    for sd in (0.5, 2.0, 4.0):
        for rate in (0.35, 0.7, 0.9):
            mean = grade_mean(min_grade=5.0, grade_sd=sd, approval_rate=rate)
            grades = [
                grade_for_attempt(quantile=q / 40_000, grade_mean=mean, grade_sd=sd)
                for q in range(1, 40_000)
            ]
            realized = sum(g >= 5.0 for g in grades) / len(grades)
            assert abs(realized - rate) < 0.01


def test_the_grade_quantile_is_drawn_fresh_for_every_attempt():
    """Não há posição permanente do aluno: duas tentativas da mesma matéria são"""
    disciplines = [Discipline("D1", seats=5, hours=1), Discipline("D2", seats=5, hours=1)]
    config = SimulationConfig(
        disciplines=[Discipline("D1", seats=5, hours=1, entry=True), disciplines[1]],
        students_per_entry_class=4,
        max_residence=3,
        **single_axis(360),
        max_hours=360,
    )
    students = generate_students(config, np.random.default_rng(0))
    quantiles = draw_grade_quantiles(
        students, config.disciplines, config, np.random.default_rng(0)
    )
    chave = (students[0].id, "D1")
    por_tentativa = [
        quantiles[(chave[0], chave[1], k)] for k in range(config.attempt_cap())
    ]
    assert len(set(por_tentativa)) == len(por_tentativa)
    assert all(0.0 <= q <= 1.0 for q in quantiles.values())


def test_the_drawn_row_covers_the_whole_grade():
    """O interesse é o sorteio cru: uma entrada por disciplina, positiva e sem"""
    config = make_config()
    students = generate_students(config, np.random.default_rng(3))
    rows = draw_interest(students, config, np.random.default_rng(3))

    assert set(rows) == {
        (s.id, period) for s in students for period in range(1, config.periods + 1)
    }
    for row in rows.values():
        assert set(row) == {d.name for d in GRADE}
        assert all(value > 0 for value in row.values())
        assert len(set(row.values())) == len(row)


def test_a_wider_sigma_makes_the_student_differentiate_more():
    """É o que sigma existe para controlar, e o papel que o expoente de afinidade"""
    flat_grade = [
        Discipline("A", seats=20, hours=60, entry=True),
        Discipline("B", seats=20, hours=60, entry=True),
        Discipline("C", seats=20, hours=60, entry=True),
        Discipline("D", seats=20, hours=60, entry=True),
    ]
    flat_kw = dict(disciplines=flat_grade, max_hours=240)
    students = generate_students(make_config(**flat_kw), np.random.default_rng(2))

    def spread(sigma: float) -> float:
        config = make_config(**flat_kw, interest_sigma=sigma)
        rows = draw_interest(students, config, np.random.default_rng(2))
        ratios = [max(row.values()) / min(row.values()) for row in rows.values()]
        return sum(ratios) / len(ratios)

    assert spread(0.25) < spread(1.0) < spread(3.0)
    flat = draw_interest(
        students,
        make_config(**flat_kw, interest_sigma=1e-4),
        np.random.default_rng(2),
    )
    assert all(
        max(row.values()) / min(row.values()) == pytest.approx(1.0, abs=5e-3)
        for row in flat.values()
    )


def test_the_draw_is_always_positive():
    """A log-normal só chegaria a zero com expoente abaixo de -745, o que não"""
    for sigma in (0.1, 1.0, 10.0):
        config = make_config(interest_sigma=sigma)
        students = generate_students(config, np.random.default_rng(11))
        rows = draw_interest(students, config, np.random.default_rng(11))
        assert rows
        for row in rows.values():
            assert min(row.values()) > 0


def test_the_guard_never_fires_in_practice():
    """A guarda é insurance, não mecanismo: em sigma nenhum razoável ela encosta"""
    config = make_config(interest_sigma=3.0)
    students = generate_students(config, np.random.default_rng(12))
    for row in draw_interest(students, config, np.random.default_rng(12)).values():
        assert all(value > UNDERFLOW_GUARD for value in row.values())


def test_the_distribution_histogram_describes_one_students_row():
    """O histograma reescala **cada linha** ao próprio [mínimo, máximo]. Global"""
    flat_grade = [
        Discipline("A", seats=20, hours=60, entry=True),
        Discipline("B", seats=20, hours=60, entry=True),
        Discipline("C", seats=20, hours=60, entry=True),
        Discipline("D", seats=20, hours=60, entry=True),
    ]
    flat_kw = dict(disciplines=flat_grade, max_hours=240)
    config = make_config(**flat_kw, interest_sigma=1.0)
    students = generate_students(config, np.random.default_rng(13))
    rows = draw_interest(students, config, np.random.default_rng(13))

    fractions = interest_distribution(rows)
    assert len(fractions) == DISTRIBUTION_BINS
    assert sum(fractions) == pytest.approx(1.0)
    assert all(value >= 0 for value in fractions)
    assert fractions[-1] > 0

    def first_bin(sigma: float) -> float:
        at = make_config(**flat_kw, interest_sigma=sigma)
        return interest_distribution(
            draw_interest(generate_students(at, np.random.default_rng(13)), at, np.random.default_rng(13))
        )[0]

    assert first_bin(0.25) < first_bin(1.0) < first_bin(3.0)


def test_only_the_zeros_change_between_periods():
    """O cerne do modelo: a linha é uma só para a simulação inteira. O que muda"""
    config = make_config()
    students = generate_students(config, np.random.default_rng(4))
    row = draw_interest(students, config, np.random.default_rng(4))[(students[0].id, 1)]

    novice = Student(id="x", name="X", credits=10)
    veteran = Student(id="x", name="X", credits=10, grades={"D1": 9.0})
    first = utility_matrix(interest=row, student=novice, config=config)
    second = utility_matrix(interest=row, student=veteran, config=config)

    assert set(first) == {"D1", "D2"}
    assert set(second) == {"D2", "D3"}
    assert sum(first.values()) == pytest.approx(sum(second.values()))


def test_the_eligible_sum_is_always_one():
    """A redistribuição conserva a massa do interesse, então a utilidade"""
    config = make_config()
    students = generate_students(config, np.random.default_rng(6))
    row = draw_interest(students, config, np.random.default_rng(6))[(students[0].id, 1)]

    novice = Student(id="x", name="X", credits=10)
    partial = sum(utility_matrix(interest=row, student=novice, config=config).values())
    assert partial == pytest.approx(1.0)

    flat = SimulationConfig(
        disciplines=[Discipline(name, seats=20, hours=60, entry=True) for name in ("A", "B", "C")],
        students_per_entry_class=8,
        max_hours=WORKLOAD,
        **single_axis(WORKLOAD),
    )
    flat_row = draw_interest(
        generate_students(flat, np.random.default_rng(6)), flat, np.random.default_rng(6)
    )[("a00000", 1)]
    whole = utility_matrix(interest=flat_row, student=Student("x", "X", 10), config=flat)
    assert sum(whole.values()) == pytest.approx(1.0)


def test_the_workload_cap_bounds_the_enrolled_hours():
    """W_a é do cenário e morde onde há mais elegíveis do que ele comporta: duas"""
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
            students_per_entry_class=10,
            max_hours=max_hours,
            **single_axis(max_hours),
            seed=5,
        )
        result = run_simulation(config)
        return [r.enrolled_hours for h in result.histories for r in h.periods]

    tight, roomy = loads(120), loads(300)
    assert max(tight) <= 120
    assert max(roomy) <= 300
    assert max(roomy) > 120


def test_the_cohort_axis_partitions_the_university():
    """O recorte fatia a mesma população do agregado: somá-lo reproduz"""
    result = run_simulation(make_config(periods=6))
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
    """As gerações entram em períodos consecutivos, todas do mesmo tamanho — o"""
    config = make_config(periods=6)
    students = generate_students(config, np.random.default_rng(0))
    assert len(students) == 8 * 6
    sizes = {entry: 0 for entry in range(1, 7)}
    for student in students:
        sizes[student.entry_period] += 1
    assert sizes == {entry: 8 for entry in range(1, 7)}


def _rows(fluctuation, periods=8, **overrides):
    disciplines = [
        Discipline(f"D{i}", seats=50, hours=60, entry=True) for i in range(1, 21)
    ]
    config = SimulationConfig(
        disciplines=disciplines,
        periods=periods,
        max_hours=20 * 60,
        interest_fluctuation=fluctuation,
        slots=20,
        **single_axis(20 * 60),
        **overrides,
    )
    students = [Student(id=f"a{i:03d}", name=f"Aluno {i}", credits=10) for i in range(400)]
    return config, draw_interest(students, config, np.random.default_rng(3))


def test_the_fluctuation_does_not_touch_the_dispersion_of_a_period():
    """A reflexão preserva a marginal: cada período continua com a dispersão"""
    spreads = []
    for fluctuation in (0.0, 0.5, 2.0):
        _, rows = _rows(fluctuation)
        logs = [np.log(v) for row in rows.values() for v in row.values()]
        spreads.append(float(np.std(logs)))
    assert max(spreads) - min(spreads) < 0.05


def test_without_fluctuation_the_preference_never_changes():
    _, rows = _rows(0.0, periods=4)
    for sid in sorted({s for s, _ in rows}):
        assert rows[(sid, 1)] == rows[(sid, 4)]


def test_a_discipline_can_carry_its_own_fluctuation():
    """Declarar por disciplina é o que sincroniza a persistência entre"""
    disciplines = [
        Discipline(f"FIXA{i}", seats=50, hours=60, entry=True, fluctuation=0.0)
        for i in range(10)
    ] + [
        Discipline(f"SOLTA{i}", seats=50, hours=60, entry=True, fluctuation=2.0)
        for i in range(10)
    ]
    config = SimulationConfig(
        disciplines=disciplines,
        periods=4,
        max_hours=20 * 60,
        interest_fluctuation=2.0,
        slots=20,
        **single_axis(20 * 60),
    )
    students = [Student(id=f"a{i:03d}", name=f"Aluno {i}", credits=10) for i in range(400)]
    rows = draw_interest(students, config, np.random.default_rng(7))
    ids = sorted({sid for sid, _ in rows})

    def lag_correlation(prefix: str) -> float:
        names = [d.name for d in disciplines if d.name.startswith(prefix)]
        first = [np.log(rows[(sid, 1)][n]) for sid in ids for n in names]
        later = [np.log(rows[(sid, 4)][n]) for sid in ids for n in names]
        return float(np.corrcoef(first, later)[0, 1])

    assert lag_correlation("FIXA") > 0.9
    assert abs(lag_correlation("SOLTA")) < 0.2


def _config_for(disciplines, **overrides):
    base = dict(
        disciplines=disciplines,
        periods=3,
        students_per_entry_class=12,
        max_hours=240,
        seed=11,
        **single_axis(240),
    )
    return SimulationConfig(**{**base, **overrides})


def _rows_for(disciplines, **overrides):
    config = _config_for(disciplines, **overrides)
    rng = np.random.default_rng(config.seed)
    return draw_interest(generate_students(config, rng), config, rng)


def test_the_same_seed_gives_the_same_grades():
    """Determinismo de ponta a ponta: a mesma seed devolve a mesma simulação,"""
    config = make_config(seed=11)
    first, second = run_simulation(config), run_simulation(make_config(seed=11))

    def grades(result):
        return [
            (summary.id, period.period, record.discipline, record.grade)
            for summary, history in zip(result.students, result.histories)
            for period in history.periods
            for record in period.requests
        ]

    assert grades(first) == grades(second)
    assert grades(first) != grades(run_simulation(make_config(seed=12)))
