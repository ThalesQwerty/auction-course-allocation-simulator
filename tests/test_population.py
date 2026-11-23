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
    draw_interest,
    interest_distribution,
    utility_matrix,
)
from profiles import single_axis
from disciplines import disciplines_from_predecessors
from leilao.config import (
    DEFAULT_PERFORMANCE,
    Discipline,
    SimulationConfig,
)
from leilao.equations import (
    attempt_rates,
    grade_shape,
    split_normal_cdf,
    split_normal_mean,
)
from leilao.grading import GradeShapes, draw_base_quantiles, grade_for_attempt
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
        **single_axis(WORKLOAD),
        seed=7,
    )
    return SimulationConfig(**{**base, **overrides})


# --- a matriz de notas -----------------------------------------------------


def _grade_config(disciplines, **overrides):
    return SimulationConfig(
        disciplines=disciplines,
        # As 40 disciplinas são todas de entrada: o ingressante cursaria as 40
        # de uma vez, e a eq. (4) tem de caber. E um horário para cada, senão
        # o pacote garantido choca consigo mesmo.
        max_hours=40 * 60,
        slots=40,
        **single_axis(40 * 60),
        **overrides,
    )


def test_the_base_quantile_is_drawn_once_per_pair_and_persists():
    """O desempenho base é **traço**: um quantil por (aluno, disciplina), sem
    dimensão de período — e é o único sorteio que a nota usa. Guardar a posição,
    e não a nota, é o que deixa a dificuldade mover a distribuição sob o aluno
    sem mexer em quem ele é."""
    disciplines = [Discipline(f"D{i}", seats=50, hours=60, entry=True) for i in range(1, 41)]
    students = [Student(id=f"a{i:03d}", name=f"Aluno {i}", credits=10) for i in range(120)]
    config = _grade_config(disciplines, periods=3)

    quantiles = draw_base_quantiles(students, disciplines, config, np.random.default_rng(0))
    assert len(quantiles) == 120 * 40
    assert all(0.0 <= q <= 1.0 for q in quantiles.values())
    # Uniforme em (0, 1): a média é 1/2.
    assert abs(sum(quantiles.values()) / len(quantiles) - 0.5) < 0.01


def test_the_profile_gives_back_exactly_the_three_quantities_asked():
    """A conversão é exata: o perfil é editado em nota mais provável, chance de
    0 e chance de 10, e é isso que a distribuição entrega. É o que torna o
    parâmetro legível — e o que faz a chance de tirar 10 ser declarada, em vez
    de consequência escondida da forma."""
    for mode_grade, zero_rate, max_rate in (
        (9.0, 0.0005, 0.030),
        (8.0, 0.0050, 0.008),
        (6.5, 0.0300, 0.0015),
    ):
        mode, left_sd, right_sd = grade_shape(
            mode_grade=mode_grade, zero_rate=zero_rate, max_rate=max_rate
        )
        shape = {"mode": mode, "left_sd": left_sd, "right_sd": right_sd}
        # A moda entra direto: o número digitado é o pico da curva.
        assert mode == mode_grade
        # Os limiares são os da nota arredondada, não os da escala.
        assert abs(split_normal_cdf(value=0.05, **shape) - zero_rate) < 1e-12
        assert abs(1.0 - split_normal_cdf(value=9.95, **shape) - max_rate) < 1e-12


def test_the_mean_is_derived_and_sits_below_the_mode():
    """A média não é parâmetro: ela sai da forma, e fica **abaixo** da moda
    porque a cauda esquerda é longa. É o que permite parametrizar pela moda sem
    faixa inviável — com a média presa, moda alta com poucos dezes não fecharia.
    """
    for mode_grade, zero_rate, max_rate in (
        (9.0, 0.0005, 0.030),
        (8.0, 0.0050, 0.008),
        (6.5, 0.0300, 0.0015),
    ):
        mode, left_sd, right_sd = grade_shape(
            mode_grade=mode_grade, zero_rate=zero_rate, max_rate=max_rate
        )
        mean = split_normal_mean(mode=mode, left_sd=left_sd, right_sd=right_sd)
        assert mean < mode_grade
        assert 1.0 < mode_grade - mean < 2.0


def test_every_mode_inside_the_scale_resolves():
    """Toda trinca existe: a moda é a locação, então qualquer valor dentro da
    escala tem forma. Só as duas chances podem não caber juntas."""
    for mode_grade in (0.5, 2.0, 5.0, 8.0, 9.5):
        grade_shape(mode_grade=mode_grade, zero_rate=0.01, max_rate=0.01)

    with pytest.raises(ValueError, match="escala"):
        grade_shape(mode_grade=10.0, zero_rate=0.01, max_rate=0.01)
    with pytest.raises(ValueError, match="somam"):
        grade_shape(mode_grade=5.0, zero_rate=0.6, max_rate=0.5)


def test_difficulty_and_attempt_enter_as_reciprocal_exponents():
    """As duas chances sobem e descem por expoentes recíprocos, e daí sai a lei
    de potência da prática: **dificuldade 2 na segunda tentativa reproduz
    dificuldade 1 na primeira**, exatamente."""
    base = {"zero_rate": 0.005, "max_rate": 0.008}

    assert attempt_rates(**base, difficulty=1.0, attempt=1) == attempt_rates(
        **base, difficulty=2.0, attempt=2
    )
    assert attempt_rates(**base, difficulty=3.0, attempt=2) == attempt_rates(
        **base, difficulty=1.5, attempt=1
    )

    # Mais difícil: zera mais, tira 10 menos. Recursar faz o contrário.
    harder_zero, harder_max = attempt_rates(**base, difficulty=2.0, attempt=1)
    again_zero, again_max = attempt_rates(**base, difficulty=1.0, attempt=2)
    assert harder_zero > base["zero_rate"] > again_zero
    assert harder_max < base["max_rate"] < again_max


def test_the_transformation_holds_the_mode_not_the_mean():
    """A dificuldade move a distribuição segurando a **moda**. Se segurasse a
    média, a moda sairia de [0, 10] assim que a dificuldade passasse de 2 — e
    deixaria de existir nota que a realizasse. Segurando a moda, a média cai
    com a dificuldade, que é o comportamento que se quer."""
    shapes = GradeShapes()
    profile = DEFAULT_PERFORMANCE
    base_mode = shapes.mode(profile)

    means = []
    for difficulty in (0.5, 1.0, 1.5, 2.0, 3.0):
        mode, left_sd, right_sd = shapes.of(profile, difficulty, 1)
        assert mode == base_mode
        assert 0.0 <= mode <= 10.0
        means.append(split_normal_mean(mode=mode, left_sd=left_sd, right_sd=right_sd))

    assert means == sorted(means, reverse=True)


def test_the_grade_stays_on_the_scale_and_reaches_both_ends():
    """O latente é ilimitado; o que limita é o instrumento. Arredondar em
    décimos e clipar em [0, 10] é o que torna 0 e 10 **alcançáveis** — e com a
    frequência que o perfil declarou, não com a de uma cauda contínua, que é a
    ordem de 10⁻⁷ e nunca sai."""
    mode, left_sd, right_sd = grade_shape(
        mode_grade=8.0, zero_rate=0.0050, max_rate=0.008
    )
    shape = {"mode": mode, "left_sd": left_sd, "right_sd": right_sd}
    grades = [
        grade_for_attempt(quantile=q / 20_000, **shape) for q in range(1, 20_000)
    ]
    assert all(0.0 <= g <= 10.0 for g in grades)
    assert min(grades) == 0.0
    assert max(grades) == 10.0
    # E a frequência bate com o que o perfil pediu.
    assert abs(sum(g >= 10.0 for g in grades) / len(grades) - 0.008) < 0.002
    assert abs(sum(g <= 0.0 for g in grades) / len(grades) - 0.0050) < 0.002


# --- o interesse e a utilidade --------------------------------------------


def test_the_drawn_row_sums_to_one_over_the_whole_grade():
    """Passo 3 da construção: a linha é dividida pelo somatório, então vale 1
    sobre a grade inteira — antes de qualquer recorte por elegibilidade."""
    config = make_config()
    students = generate_students(config, np.random.default_rng(3))
    rows = draw_interest(students, config, np.random.default_rng(3))

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
        config = make_config(**flat_kw, interest_sigma=sigma)
        rows = draw_interest(students, config, np.random.default_rng(2))
        ratios = [max(row.values()) / min(row.values()) for row in rows.values()]
        return sum(ratios) / len(ratios)

    assert spread(0.25) < spread(1.0) < spread(3.0)
    # Sigma minúsculo é indiferença: a linha converge para 1/|B|.
    flat = draw_interest(
        students,
        make_config(**flat_kw, interest_sigma=1e-4),
        np.random.default_rng(2),
    )
    assert all(
        value == pytest.approx(1 / len(flat_grade), abs=5e-3)
        for row in flat.values()
        for value in row.values()
    )


def test_the_mean_is_only_scale():
    """μ multiplica a linha inteira por e^μ, e a normalização desfaz o fator:
    o interesse normalizado é o mesmo para qualquer μ. Ele existe para a
    prévia da interface, e se um dia passar a mexer na alocação, é bug."""
    config = make_config()
    students = generate_students(config, np.random.default_rng(14))

    def rows(mean: float) -> dict:
        at = make_config(interest_mean=mean)
        return draw_interest(students, at, np.random.default_rng(14))

    reference = rows(0.0)
    for mean in (-3.0, 1.0, 5.0):
        shifted = rows(mean)
        assert shifted.keys() == reference.keys()
        for key, row in shifted.items():
            assert row == pytest.approx(reference[key], rel=1e-12)


def test_the_draw_is_always_positive():
    """A log-normal só chegaria a zero com expoente abaixo de -745, o que não
    acontece em sigma nenhum que faça sentido — mas a invariante importa: zero
    marca o **inelegível**, e as duas mochilas filtram por `utilidade > 0`. Uma
    utilidade nula tiraria a disciplina do conjunto de escolha e o aluno nunca a
    cursaria, nem quando fosse a única disponível."""
    for sigma in (0.1, 1.0, 10.0):
        config = make_config(interest_sigma=sigma)
        students = generate_students(config, np.random.default_rng(11))
        rows = draw_interest(students, config, np.random.default_rng(11))
        assert rows
        for row in rows.values():
            assert min(row.values()) > 0
            assert sum(row.values()) == pytest.approx(1.0)


def test_the_guard_never_fires_in_practice():
    """A guarda é insurance, não mecanismo: em sigma nenhum razoável ela encosta
    no sorteio. (A Gamma que havia antes precisava dela de verdade, e por isso a
    faixa de parâmetro utilizável era limitada.)"""
    config = make_config(interest_sigma=3.0)
    students = generate_students(config, np.random.default_rng(12))
    for row in draw_interest(students, config, np.random.default_rng(12)).values():
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
    config = make_config(**flat_kw, interest_sigma=1.0)
    students = generate_students(config, np.random.default_rng(13))
    rows = draw_interest(students, config, np.random.default_rng(13))

    fractions = interest_distribution(rows)
    assert len(fractions) == DISTRIBUTION_BINS
    assert sum(fractions) == pytest.approx(1.0)
    assert all(value >= 0 for value in fractions)
    # A última faixa guarda o máximo de cada linha, então nunca é vazia.
    assert fractions[-1] > 0

    # Sigma maior concentra: mais massa na primeira faixa, porque o máximo da
    # linha se afasta do resto.
    def first_bin(sigma: float) -> float:
        at = make_config(**flat_kw, interest_sigma=sigma)
        return interest_distribution(
            draw_interest(generate_students(at, np.random.default_rng(13)), at, np.random.default_rng(13))
        )[0]

    assert first_bin(0.25) < first_bin(1.0) < first_bin(3.0)


def test_only_the_zeros_change_between_periods():
    """O cerne do modelo: a linha é uma só para a simulação inteira. O que muda
    de um período para o outro é quem está no conjunto elegível, nunca o valor
    de quem está."""
    config = make_config()
    students = generate_students(config, np.random.default_rng(4))
    row = draw_interest(students, config, np.random.default_rng(4))[(students[0].id, 1)]

    novice = Student(id="x", name="X", credits=10)
    veteran = Student(id="x", name="X", credits=10, grades={"D1": 9.0})
    first = utility_matrix(interest=row, student=novice, config=config)
    second = utility_matrix(interest=row, student=veteran, config=config)

    # D1 sai (aprovada) e D3 entra (pré-requisito cumprido); D4 continua fora,
    # porque depende de D2.
    assert set(first) == {"D1", "D2"}
    assert set(second) == {"D2", "D3"}
    # O interesse é o mesmo nas duas utilidades — o que muda é para onde o
    # interesse do inelegível desce, e isso é função do conjunto elegível.
    assert sum(first.values()) == pytest.approx(sum(second.values()))
    assert first["D2"] >= row["D2"] and second["D2"] >= row["D2"]


def test_the_eligible_sum_is_always_one():
    """A redistribuição conserva a massa do interesse, então a utilidade
    soma 1 em qualquer estágio — substitui o U_a^(t) da eq. (43), que era
    menor que 1 sempre que algo estava fora do alcance."""
    config = make_config()
    students = generate_students(config, np.random.default_rng(6))
    row = draw_interest(students, config, np.random.default_rng(6))[(students[0].id, 1)]

    novice = Student(id="x", name="X", credits=10)
    partial = sum(utility_matrix(interest=row, student=novice, config=config).values())
    # A redistribuição conserva a massa: a utilidade soma 1 em qualquer
    # estágio do aluno, e é isso que põe `alpha_u` na mesma unidade.
    assert partial == pytest.approx(1.0)

    # Numa grade sem pré-requisito nenhum, tudo é elegível de saída e a soma é 1.
    flat = SimulationConfig(
        disciplines=[Discipline(name, seats=20, hours=60, entry=True) for name in ("A", "B", "C")],
        students_per_period=8,
        max_hours=WORKLOAD,
        **single_axis(WORKLOAD),
    )
    flat_row = draw_interest(
        generate_students(flat, np.random.default_rng(6)), flat, np.random.default_rng(6)
    )[("a00000", 1)]
    whole = utility_matrix(interest=flat_row, student=Student("x", "X", 10), config=flat)
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
            **single_axis(max_hours),
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
    """As gerações entram em períodos consecutivos, todas do mesmo tamanho — o
    ingresso não vem da seed."""
    config = make_config(periods=6)
    students = generate_students(config, np.random.default_rng(0))
    # Ingresso em todo período: |A| é a coorte vezes o horizonte.
    assert len(students) == 8 * 6
    sizes = {entry: 0 for entry in range(1, 7)}
    for student in students:
        sizes[student.entry_period] += 1
    assert sizes == {entry: 8 for entry in range(1, 7)}


# --- a estabilidade da preferência ----------------------------------------


def _rows(stability, periods=8, **overrides):
    disciplines = [
        Discipline(f"D{i}", seats=50, hours=60, entry=True) for i in range(1, 21)
    ]
    config = SimulationConfig(
        disciplines=disciplines,
        periods=periods,
        max_hours=20 * 60,
        interest_stability=stability,
        # 20 disciplinas de entrada, de turma única: o pacote garantido só
        # cabe se houver um horário para cada uma.
        slots=20,
        **single_axis(20 * 60),
        **overrides,
    )
    students = [Student(id=f"a{i:03d}", name=f"Aluno {i}", credits=10) for i in range(400)]
    return config, draw_interest(students, config, np.random.default_rng(3))


def test_stability_does_not_touch_the_dispersion_of_a_period():
    """A divisão preserva a variância: cada período continua com a dispersão de
    sigma, qualquer que seja a estabilidade. É o que a torna **ortogonal ao
    sigma** — com os pesos "intuitivos" (s e 1-s) a dispersão vazaria, e a
    estabilidade viraria um segundo botão do parâmetro de que ela precisa ser
    independente."""
    spreads = []
    for stability in (0.0, 0.5, 0.9):
        _, rows = _rows(stability)
        # Desvio do log, que é onde a divisão acontece — a normalização por
        # linha não mexe nas razões.
        logs = [np.log(v) for row in rows.values() for v in row.values()]
        spreads.append(float(np.std(logs)))
    assert max(spreads) - min(spreads) < 0.05


def test_stability_is_the_correlation_between_any_two_periods():
    """E não só entre semestres consecutivos: a peça permanente não decai, então
    a correlação entre o 1º e o 8º período é a mesma que entre o 1º e o 2º."""
    for stability in (0.0, 0.5, 0.9):
        _, rows = _rows(stability)
        ids = sorted({sid for sid, _ in rows})
        first = [rows[(sid, 1)][n] for sid in ids for n in rows[(sid, 1)]]
        for other in (2, 8):
            later = [rows[(sid, other)][n] for sid in ids for n in rows[(sid, 1)]]
            measured = np.corrcoef(np.log(first), np.log(later))[0, 1]
            assert abs(measured - stability) < 0.06, (stability, other, measured)


def test_a_fully_stable_preference_never_changes():
    _, rows = _rows(1.0, periods=4)
    for sid in sorted({s for s, _ in rows}):
        assert rows[(sid, 1)] == rows[(sid, 4)]


def test_a_discipline_can_carry_its_own_stability():
    """Declarar por disciplina é o que sincroniza a persistência entre
    concorrentes — e é a única estrutura que muda o resultado, porque é a
    sincronia, e não a persistência em si, que trava a fila.

    A prova é sobre a **correlação entre períodos de cada disciplina**, e não
    sobre a variância da cota: com poucas disciplinas as cotas são quase
    complementares, e a variância de uma espelha a da outra quer ela seja fixa
    ou não.
    """
    disciplines = [
        Discipline(f"FIXA{i}", seats=50, hours=60, entry=True, stability=1.0)
        for i in range(10)
    ] + [
        Discipline(f"SOLTA{i}", seats=50, hours=60, entry=True, stability=0.0)
        for i in range(10)
    ]
    config = SimulationConfig(
        disciplines=disciplines,
        periods=4,
        max_hours=20 * 60,
        interest_stability=0.0,
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


# --- a rotina e o turno ----------------------------------------------------


def _config_for(disciplines, **overrides):
    base = dict(
        disciplines=disciplines,
        periods=3,
        students_per_period=12,
        max_hours=240,
        seed=11,
        **single_axis(240),
    )
    return SimulationConfig(**{**base, **overrides})


def _rows_for(disciplines, **overrides):
    config = _config_for(disciplines, **overrides)
    rng = np.random.default_rng(config.seed)
    return draw_interest(generate_students(config, rng), config, rng)


def test_the_classes_of_a_discipline_are_not_systematically_ordered():
    """Com o turno fora do modelo, nada separa as turmas de uma disciplina de
    forma **correlacionada** entre alunos: o que resta é o desvio sorteado por
    `class_stability`, independente de aluno para aluno.

    O teste guarda a consequência: a razão **mediana** entre duas turmas irmãs
    fica em 1, em vez de refletir uma ordem fixa da grade. A mediana e não a
    média porque a razão entre duas log-normais independentes tem cauda
    pesada — a média dela é e^(σ²), e não 1, sem que nada esteja enviesado.
    """
    disciplinas = [Discipline(name="X", seats=600, hours=60, classes=3, entry=True)]
    rows = _rows_for(disciplinas, class_stability=0.0, students_per_period=60)
    razoes = [row["X T3"] / row["X T1"] for row in rows.values()]
    assert np.median(razoes) == pytest.approx(1.0, abs=0.15)


def test_every_class_keeps_a_positive_interest():
    """A normalização reparte, nunca zera: toda turma segue no conjunto de
    escolha do aluno."""
    disciplinas = [Discipline(name="X", seats=600, hours=60, classes=3, entry=True)]
    rows = _rows_for(disciplinas, class_stability=0.0)
    assert all(row["X T3"] > 0 for row in rows.values())


def test_the_performance_profile_does_not_move_anyone_elses_draw():
    """Seção 7.3: a seed define **todos** os sorteios, e mexer num parâmetro
    não pode deslocar o fluxo do gerador para os outros.

    A Beta da aptidão não garantia isso: ela é gerada por rejeição e consome um
    número **variável** de uniformes por amostra, de modo que recalibrar um
    perfil mudava a posição do fluxo e, com ela, o sorteio de todo mundo que
    vinha depois. O quantil consome exatamente um valor por célula, e por isso
    o desenho da matriz não depende de perfil nenhum.
    """
    disciplines = [Discipline(f"D{i}", seats=50, hours=60, entry=True) for i in range(1, 6)]
    students = [Student(id=f"a{i:03d}", name=f"Aluno {i}", credits=10) for i in range(50)]
    config = _grade_config(disciplines, periods=2)

    first = draw_base_quantiles(students, disciplines, config, np.random.default_rng(0))
    harder = [
        Student(id=s.id, name=s.name, credits=10,
                performance_level=0.0)
        for s in students
    ]
    second = draw_base_quantiles(harder, disciplines, config, np.random.default_rng(0))

    assert first == second


def test_the_same_seed_gives_the_same_grades():
    """Determinismo de ponta a ponta: a mesma seed devolve a mesma simulação,
    nota por nota. Nada é sorteado dentro do laço."""
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
