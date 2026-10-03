"""Perfis de aluno: aptidão (a normal das notas) e afinidade (o expoente sobre
a matriz de utilidades). Os dois eixos são independentes, e a repartição da
população entre eles é exata, não sorteada."""
import numpy as np
import pytest

from leilao.behavior import draw_utilities, utility_matrix
from leilao.config import (
    DEFAULT_AFFINITY,
    DEFAULT_APTITUDE,
    AffinityProfile,
    AptitudeProfile,
    Discipline,
    SimulationConfig,
    apportion,
)
from leilao.grading import initial_grades
from leilao.population import Student, generate_students
from leilao.simulation import run_simulation

APTITUDE = [
    AptitudeProfile("Exemplar", mean=8, stddev=1, share=25),
    AptitudeProfile("Regular", mean=6.5, stddev=1.5, share=50),
    AptitudeProfile("Instável", mean=5, stddev=2, share=25),
]
# W_a dos perfis: a grade tem 4 disciplinas de 60 h, 2 por período.
WORKLOAD = 180

AFFINITY = [
    AffinityProfile("Focados", kind="concentrated", intensity=2, max_hours=WORKLOAD, share=50),
    AffinityProfile("Dispersos", kind="diluted", intensity=2, max_hours=WORKLOAD, share=50),
]

GRADE = [
    Discipline("D1", seats=20, hours=60),
    Discipline("D2", seats=20, hours=60),
    Discipline("D3", seats=20, hours=60, prerequisites=("D1",)),
    Discipline("D4", seats=20, hours=60, prerequisites=("D2",)),
]


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=5,
        students_per_period=8,
        aptitude_profiles=APTITUDE,
        affinity_profiles=AFFINITY,
        seed=7,
    )
    return SimulationConfig(**{**base, **overrides})


# --- repartição -----------------------------------------------------------


def test_apportion_splits_whole_units_by_largest_remainder():
    assert apportion(10, [50, 50]) == [5, 5]
    # 1/3 de 10 é 3,33: três inteiros e a sobra para as maiores frações.
    assert apportion(10, [1, 1, 1]) == [4, 3, 3]
    assert sum(apportion(37, [25, 50, 25])) == 37
    assert apportion(0, [50, 50]) == [0, 0]
    assert apportion(5, []) == []


def test_the_joint_share_is_the_product_of_the_two_axes():
    """Dois perfis de 50% em cada eixo dão 25% para cada uma das quatro
    combinações — é o que "a % tem de ser igual em todos os recortes" quer
    dizer: os eixos são independentes."""
    config = make_config(
        # A geração inteira entra com vaga garantida nas de 1º período, então a
        # oferta de lá precisa comportá-la.
        disciplines=[Discipline("D1", seats=40, hours=60), Discipline("D2", seats=40, hours=60)],
        students_per_period=40,
        aptitude_profiles=[
            AptitudeProfile("A", mean=7, stddev=1, share=50),
            AptitudeProfile("B", mean=5, stddev=1, share=50),
        ],
    )
    mix = config.generation_profiles()
    assert len(mix) == 40
    counts: dict[tuple[str, str], int] = {}
    for aptitude, affinity in mix:
        key = (aptitude.name, affinity.name)
        counts[key] = counts.get(key, 0) + 1
    assert counts == {
        ("A", "Focados"): 10,
        ("A", "Dispersos"): 10,
        ("B", "Focados"): 10,
        ("B", "Dispersos"): 10,
    }


def test_every_generation_has_the_same_profile_mix():
    """A repartição é por geração, não sobre a população inteira: sem isso o
    perfil ficaria correlacionado com o período de ingresso, e o recorte por
    geração mediria perfil junto com senioridade."""
    config = make_config(students_per_period=8, periods=5)
    students = generate_students(config, np.random.default_rng(config.seed))
    by_entry: dict[int, list[tuple[str, str]]] = {}
    for student in students:
        by_entry.setdefault(student.entry_period, []).append(
            (student.aptitude.name, student.affinity.name)
        )
    mixes = [sorted(members) for members in by_entry.values()]
    assert len(mixes) == 5
    assert all(mix == mixes[0] for mix in mixes)


def test_the_profile_mix_does_not_come_from_the_seed():
    """Duas seeds diferentes têm a mesma composição de perfis: o que a seed
    sorteia são as notas e as preferências, não quem é de que perfil."""
    config = make_config(seed=1)
    other = make_config(seed=999)
    assign = lambda c: [  # noqa: E731
        (s.aptitude.name, s.affinity.name)
        for s in generate_students(c, np.random.default_rng(c.seed))
    ]
    assert assign(config) == assign(other)


def test_shares_that_do_not_add_up_are_rejected():
    for axis, profiles in (
        ("aptitude_profiles", [AptitudeProfile("A", mean=7, stddev=1, share=40)]),
        (
            "affinity_profiles",
            [AffinityProfile("A", kind="concentrated", intensity=1, share=140)],
        ),
    ):
        with pytest.raises(ValueError, match="precisam somar 100%"):
            make_config(**{axis: profiles})


def test_an_empty_profile_list_is_rejected():
    with pytest.raises(ValueError, match="pelo menos um perfil de aptidão"):
        make_config(aptitude_profiles=[])
    with pytest.raises(ValueError, match="pelo menos um perfil de afinidade"):
        make_config(affinity_profiles=[])


def test_duplicate_profile_names_are_rejected():
    with pytest.raises(ValueError, match="perfis de aptidão com nomes repetidos"):
        make_config(
            aptitude_profiles=[
                AptitudeProfile("A", mean=7, stddev=1, share=50),
                AptitudeProfile("A", mean=5, stddev=1, share=50),
            ]
        )


def test_the_default_profiles_are_neutral():
    """Omitir os perfis dá uma população homogênea e sem distorção — que é o
    comportamento de um cenário montado antes de os perfis existirem."""
    config = SimulationConfig(disciplines=GRADE, students_per_period=4)
    assert config.aptitude_profiles == [DEFAULT_APTITUDE]
    assert config.affinity_profiles == [DEFAULT_AFFINITY]
    assert DEFAULT_AFFINITY.exponent == 1.0
    # Os dois parâmetros que vivem no perfil começam no valor neutro.
    assert DEFAULT_AFFINITY.max_hours == 360
    assert DEFAULT_APTITUDE.learning_gain == 2.5


# --- aptidão --------------------------------------------------------------


def test_grades_follow_the_normal_of_each_aptitude_profile():
    """Muitos sorteios por perfil: a média amostral tem de cair perto da média
    do perfil, e a dispersão tem de ordenar os perfis como eles pedem."""
    disciplines = [Discipline(f"D{i}", seats=50, hours=60) for i in range(1, 41)]
    students = [
        Student(
            id=f"a{i:03d}",
            name=f"Aluno {i}",
            aptitude=APTITUDE[i % len(APTITUDE)],
            affinity=DEFAULT_AFFINITY,
            credits=10,
        )
        for i in range(120)
    ]
    grades = initial_grades(students, disciplines, np.random.default_rng(0))

    for profile in APTITUDE:
        sample = [
            grade
            for (student_id, _), grade in grades.items()
            for student in students
            if student.id == student_id and student.aptitude is profile
        ]
        assert len(sample) > 1000
        # Truncada em [0, 10], a média amostral puxa para cima nos perfis
        # baixos; meio ponto de folga cobre isso sem esconder uma troca de
        # perfil, que custaria 1,5 ponto.
        assert abs(sum(sample) / len(sample) - profile.mean) < 0.5
        assert all(0 <= grade <= 10 for grade in sample)


def test_a_higher_aptitude_profile_performs_better():
    """O que o eixo existe para medir: a aptidão aparece no resultado, e na
    direção certa. O CR ordena os três perfis, e o tempo até a conclusão os
    ordena ao contrário — quem reprova mais recursa mais e demora mais.

    A medida é o CR e o tempo, não a *taxa* de conclusão: com o incremento de
    aprendizado, quem reprova acaba passando na recursada, então num horizonte
    folgado todos os perfis chegam ao fim e a taxa empata em 100%. O que a
    aptidão muda é quanto custa chegar lá.
    """
    result = run_simulation(make_config(periods=6, entry_periods=3))
    grades: dict[str, list[float]] = {}
    spans: dict[str, list[int]] = {}
    for student in result.students:
        grades.setdefault(student.aptitude, []).append(student.grade_average)
        if student.graduated_at is not None:
            spans.setdefault(student.aptitude, []).append(
                student.graduated_at - student.entry_period + 1
            )
    mean = lambda values: sum(values) / len(values)  # noqa: E731
    assert mean(grades["Exemplar"]) > mean(grades["Regular"]) > mean(grades["Instável"])
    assert mean(spans["Exemplar"]) < mean(spans["Regular"]) < mean(spans["Instável"])


# --- afinidade ------------------------------------------------------------


def test_a_concentrated_profile_spreads_the_utilities_further_apart():
    """O expoente > 1 afasta as utilidades; < 1 as aproxima. A razão entre a
    maior e a menor é a leitura direta disso."""
    config = make_config()
    draw = draw_utilities(
        [Student("a1", "Fulano", APTITUDE[0], AFFINITY[0], credits=10)],
        config,
        np.random.default_rng(4),
    )[("a1", 1)]

    def spread(profile: AffinityProfile) -> float:
        student = Student("a1", "Fulano", APTITUDE[0], profile, credits=10)
        values = utility_matrix(draw=draw, student=student, config=config).values()
        return max(values) / min(values)

    neutral = AffinityProfile("Neutro", kind="concentrated", intensity=1, share=100)
    assert spread(AFFINITY[1]) < spread(neutral) < spread(AFFINITY[0])


def test_the_affinity_exponent_keeps_the_spend_fraction_intact():
    """eq. (43): a soma das utilidades continua sendo U_a depois da distorção —
    é para isso que a matriz é dividida pelo somatório no fim."""
    config = make_config()
    draws = draw_utilities(
        [Student("a1", "Fulano", APTITUDE[0], AFFINITY[0], credits=10)],
        config,
        np.random.default_rng(6),
    )
    for profile in [*AFFINITY, AffinityProfile("Forte", "concentrated", 10, WORKLOAD, 100)]:
        student = Student("a1", "Fulano", APTITUDE[0], profile, credits=10)
        for period in range(1, config.periods + 1):
            utilities = utility_matrix(
                draw=draws[("a1", period)], student=student, config=config
            )
            assert sum(utilities.values()) == pytest.approx(
                draws[("a1", period)].spend_fraction
            )
            assert 0 < sum(utilities.values()) <= 1


def test_a_neutral_affinity_does_not_touch_the_drawn_matrix():
    """Intensidade 1 dá expoente 1 nos dois sentidos — o perfil que não
    distorce nada, e a linha de base contra a qual os outros se leem."""
    config = make_config()
    draw = draw_utilities(
        [Student("a1", "Fulano", APTITUDE[0], DEFAULT_AFFINITY, credits=10)],
        config,
        np.random.default_rng(8),
    )[("a1", 1)]
    plain = utility_matrix(
        draw=draw,
        student=Student("a1", "Fulano", APTITUDE[0], DEFAULT_AFFINITY, credits=10),
        config=config,
    )
    diluted_one = utility_matrix(
        draw=draw,
        student=Student(
            "a1",
            "Fulano",
            APTITUDE[0],
            AffinityProfile("Um", kind="diluted", intensity=1, share=100),
            credits=10,
        ),
        config=config,
    )
    assert plain == pytest.approx(diluted_one)


def test_affinity_intensity_is_bounded():
    with pytest.raises(ValueError, match="intensidade deve ser um inteiro entre 1 e"):
        AffinityProfile("X", kind="concentrated", intensity=0, share=100)
    with pytest.raises(ValueError, match="intensidade deve ser um inteiro entre 1 e"):
        AffinityProfile("X", kind="concentrated", intensity=99, share=100)


def test_a_roomier_affinity_profile_carries_more_disciplines_per_period():
    """W_a é do perfil, e o teto morde onde há mais elegíveis do que ele comporta.

    A grade é feita para isso: duas disciplinas de 1º período (120 h, que cabem
    nos dois perfis) e cinco atrás de uma delas, de modo que no 2º período
    sobram 300 h elegíveis — mais do que o perfil apertado consegue carregar.
    """
    base = [Discipline("A", seats=50, hours=60), Discipline("B", seats=50, hours=60)]
    config = SimulationConfig(
        disciplines=[
            *base,
            *[
                Discipline(name, seats=50, hours=60, prerequisites=("A",))
                for name in ("C", "D", "E", "F", "G")
            ],
        ],
        periods=4,
        students_per_period=10,
        aptitude_profiles=[AptitudeProfile("Bom", mean=9, stddev=0.5, share=100)],
        affinity_profiles=[
            AffinityProfile("Apertado", "concentrated", 1, 120, 50),
            AffinityProfile("Folgado", "concentrated", 1, 300, 50),
        ],
        seed=5,
    )
    result = run_simulation(config)
    cap = {p.name: p.max_hours for p in config.affinity_profiles}
    affinity = {s.id: s.affinity for s in result.students}

    loaded: dict[str, list[int]] = {name: [] for name in cap}
    for history in result.histories:
        for record in history.periods:
            assert record.enrolled_hours <= cap[affinity[history.student_id]]
            loaded[affinity[history.student_id]].append(record.enrolled_hours)

    # O teto folgado de fato é usado: alguém carrega mais do que o apertado
    # jamais poderia.
    assert max(loaded["Folgado"]) > cap["Apertado"]
    assert max(loaded["Apertado"]) <= cap["Apertado"]


def test_a_bigger_learning_gain_recovers_a_failure_faster():
    """O incremento é do perfil de aptidão: com a mesma nota de partida, quem
    tem o ganho maior volta a passar antes."""
    config = SimulationConfig(
        disciplines=[Discipline("A", seats=50, hours=60)],
        periods=6,
        students_per_period=10,
        aptitude_profiles=[
            # Mesma distribuição de notas, ganhos diferentes: o que separa os
            # dois perfis é só o quanto a recursada acrescenta.
            AptitudeProfile("Lento", mean=2, stddev=0.1, learning_gain=0.5, share=50),
            AptitudeProfile("Rápido", mean=2, stddev=0.1, learning_gain=3.0, share=50),
        ],
        seed=8,
    )
    result = run_simulation(config)
    attempts: dict[str, list[int]] = {"Lento": [], "Rápido": []}
    aptitude = {s.id: s.aptitude for s in result.students}
    for history in result.histories:
        for record in history.periods:
            for request in record.requests:
                if request.approved:
                    attempts[aptitude[history.student_id]].append(request.attempt)
                    break
            else:
                continue
            break
    assert attempts["Rápido"], "o perfil rápido deveria aprovar dentro do horizonte"
    mean = lambda values: sum(values) / len(values)  # noqa: E731
    assert not attempts["Lento"] or mean(attempts["Rápido"]) < mean(attempts["Lento"])

# --- recortes do relatório -------------------------------------------------


def test_each_profile_axis_partitions_the_university():
    """Os três recortes fatiam a mesma população: somar qualquer um deles
    reproduz o agregado, em toda rodada e todo período."""
    result = run_simulation(make_config(periods=6, entry_periods=3))
    reports = [r for p in result.periods for r in (*p.rounds, p.aggregate)]
    assert reports

    for report in reports:
        for axis in (report.by_cohort, report.by_aptitude, report.by_affinity):
            assert sum(g.active for g in axis) == report.overall.active
            assert sum(g.population for g in axis) == report.overall.population
            assert sum(g.graduated for g in axis) == report.overall.graduated
            keys = [g.group for g in axis]
            assert len(set(keys)) == len(keys)
            assert all(key is not None for key in keys)


def test_profile_axes_keep_the_order_and_the_names_of_the_scenario():
    """A ordem das séries é a ordem em que o cenário declara os perfis, e todo
    perfil aparece em todo período — mesmo sem aluno ativo, para a série não
    sumir no meio do gráfico."""
    config = make_config(periods=6)
    result = run_simulation(config)
    assert result.aptitude_profiles == [p.name for p in APTITUDE]
    assert result.affinity_profiles == [p.name for p in AFFINITY]
    for period in result.periods:
        for report in (*period.rounds, period.aggregate):
            assert [g.group for g in report.by_aptitude] == result.aptitude_profiles
            assert [g.group for g in report.by_affinity] == result.affinity_profiles


def test_the_student_summary_carries_both_profiles():
    result = run_simulation(make_config())
    assert {s.aptitude for s in result.students} == {p.name for p in APTITUDE}
    assert {s.affinity for s in result.students} == {p.name for p in AFFINITY}
