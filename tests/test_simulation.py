import numpy as np
import pytest

from leilao.config import Course, Discipline, SimulationConfig
from leilao.grading import credit_return
from leilao.metrics import demand_per_seat, jain_index, pearson, semestralization
from leilao.population import generate_students
from leilao.simulation import run_simulation


def make_config(**overrides) -> SimulationConfig:
    disciplines = [Discipline(f"D{i}", seats=6, hours=60) for i in range(1, 9)]
    base = dict(
        disciplines=disciplines,
        courses=[
            Course(
                "Computação",
                students_per_generation=2,
                hours_to_graduate=300,
                required=("D1", "D2", "D3", "D4"),
                electives=("D5", "D6"),
            ),
            Course(
                "Matemática",
                students_per_generation=1,
                hours_to_graduate=240,
                required=("D1", "D2", "D7"),
                electives=("D8",),
            ),
        ],
        periods=5,
        rounds=2,
        max_hours=180,
        seed=11,
    )
    return SimulationConfig(**{**base, **overrides})


def test_scenario_with_unreachable_graduation_is_rejected():
    # eq. (39): S_k não pode passar da carga de obrigatórias + optativas
    with pytest.raises(ValueError, match="horas para conclusão"):
        SimulationConfig(
            disciplines=[Discipline("D1", seats=1, hours=60)],
            courses=[
                Course("Curso", students_per_generation=1, hours_to_graduate=600, required=("D1",))
            ],
        )


def test_course_referencing_unknown_discipline_is_rejected():
    with pytest.raises(ValueError, match="disciplinas inexistentes"):
        SimulationConfig(
            disciplines=[Discipline("D1", seats=1, hours=60)],
            courses=[
                Course("Curso", students_per_generation=1, hours_to_graduate=0, electives=("D9",))
            ],
        )


def test_same_seed_produces_the_same_simulation():
    first = run_simulation(make_config())
    second = run_simulation(make_config())
    assert [s.grade_average for s in first.students] == [s.grade_average for s in second.students]
    assert [s.graduated_at for s in first.students] == [s.graduated_at for s in second.students]
    assert first.periods[-1].aggregate.overall == second.periods[-1].aggregate.overall


def test_different_seeds_produce_different_students():
    first = run_simulation(make_config(seed=1))
    second = run_simulation(make_config(seed=2))
    assert [s.name for s in first.students] != [s.name for s in second.students]


def test_seats_are_never_oversubscribed():
    result = run_simulation(make_config())
    for period in result.periods:
        for snapshot in period.disciplines:
            assert snapshot.filled <= snapshot.seats


def test_students_never_exceed_the_period_workload():
    config = make_config()
    result = run_simulation(config)
    hours = config.hours_by_discipline()
    max_disciplines = config.max_hours // min(hours.values())
    for period in result.periods:
        for snapshot in period.aggregate.by_course:
            assert snapshot.metrics.allocations_per_student <= max_disciplines


def test_students_graduate_and_leave_the_simulation():
    result = run_simulation(make_config(periods=12))
    graduated = [s for s in result.students if s.graduated_at is not None]
    assert graduated, "ninguém concluiu o curso em 12 períodos"

    # eq. (40): quem conclui sai e não volta. Com uma geração nova entrando a
    # cada período o total de ativos não cai — o que denuncia a saída é haver,
    # no último período, menos ativos do que gente que já ingressou.
    last = result.periods[-1]
    entered = len([s for s in result.students if s.entry_period <= last.period])
    assert last.aggregate.overall.students < entered

    # E ninguém reaparece depois de concluir.
    by_id = {s.id: s for s in result.students}
    for history in result.histories:
        student = by_id[history.student_id]
        if student.graduated_at is not None and history.periods:
            assert max(r.period for r in history.periods) <= student.graduated_at


def test_graduates_approved_every_required_discipline():
    config = make_config(periods=12)
    result = run_simulation(config)
    courses = {c.name: c for c in config.courses}
    hours = config.hours_by_discipline()
    for student in result.students:
        if student.graduated_at is None:
            continue
        course = courses[student.course]
        assert student.approved_hours >= sum(hours[name] for name in course.required)


def test_metrics_stay_within_their_theoretical_ranges():
    result = run_simulation(make_config())
    for period in result.periods:
        for report in [*period.rounds, period.aggregate]:
            for metrics in [report.overall, *(s.metrics for s in report.by_course)]:
                assert 0 <= metrics.efficiency <= 1  # eq. (53)
                assert 0 <= metrics.fairness <= 1  # eq. (55)
                assert 0 <= metrics.occupancy <= 1  # eq. (54)
                assert -1 <= metrics.correlation <= 1  # eq. (57)
                # Alunos por vaga: sem teto fixo — no limite a população
                # inteira disputa uma disciplina de uma vaga só.
                assert metrics.scarcity >= 0
                # Candidatos por vaga: sem teto fixo — no limite todo mundo
                # pede a mesma disciplina de uma vaga só.
                assert metrics.contention >= 0
                # Em um período o aluno aprova no máximo W_a horas, então o
                # acumulado nunca passa de W_a vezes a idade em períodos.
                assert 0 <= metrics.semestralization <= 1


def test_semestralization_is_zero_in_the_entry_period_and_one_at_full_load():
    # Idade 0: o aluno acabou de ingressar e a razão seria 0/0 — eq. não
    # definida, adotamos 0.
    assert semestralization(approved_hours=0, max_hours=120, periods_completed=0) == 0.0
    # Encheu a carga horária e passou em tudo nos dois períodos que viveu.
    assert semestralization(approved_hours=240, max_hours=120, periods_completed=2) == 1.0
    # Metade do ritmo: dois períodos para a carga de um.
    assert semestralization(approved_hours=120, max_hours=120, periods_completed=2) == 0.5


def test_demand_per_seat_is_the_mean_candidate_per_seat_ratio():
    assert demand_per_seat(demands=[2 / 10, 4 / 10]) == pytest.approx(0.3)
    # Conjunto vazio: nada elegível, ou nada pedido.
    assert demand_per_seat(demands=[]) == 0.0


def test_demand_per_seat_sees_who_else_wants_the_same_seats():
    """O que uma medida do *tamanho* da oferta não veria. Dois alunos diante de
    60 vagas: em disciplinas separadas não há disputa; na mesma, há o dobro —
    e somar vagas ao alcance daria 1/60 nos dois casos."""
    separate = [demand_per_seat(demands=[1 / 60]), demand_per_seat(demands=[1 / 60])]
    together = [demand_per_seat(demands=[2 / 60]), demand_per_seat(demands=[2 / 60])]
    assert sum(together) / len(together) == 2 * (sum(separate) / len(separate))


def test_scarcity_and_contention_are_means_over_students_not_sums():
    """Médias: a contagem de quem quer já traz a população dentro do valor de
    cada aluno. O global é a média ponderada pelos alunos de cada recorte."""
    result = run_simulation(make_config(periods=4))
    for period in result.periods:
        for report in [*period.rounds, period.aggregate]:
            for field in ("scarcity", "contention"):
                parts = [s for s in report.by_course if s.metrics]
                total = sum(getattr(s.metrics, field) * s.metrics.students for s in parts)
                assert total / report.overall.students == pytest.approx(
                    getattr(report.overall, field)
                )


def test_scarcity_counts_every_student_still_able_to_take_the_discipline():
    """No primeiro período ninguém aprovou nada: todo aluno é elegível a tudo,
    então cada disciplina tem a população inteira disputando as suas vagas."""
    config = make_config(periods=1)
    result = run_simulation(config)
    overall = result.periods[0].aggregate.overall
    expected = sum(overall.students / d.seats for d in config.disciplines) / len(
        config.disciplines
    )
    assert overall.scarcity == pytest.approx(expected)


def test_scarcity_measures_potential_demand_and_contention_the_realized_one():
    """O par: só se pede o que é elegível, então a demanda que se materializa é
    uma fração da potencial — e é a razão entre as duas que diz quanta."""
    result = run_simulation(make_config(periods=6))
    for period in result.periods:
        overall = period.aggregate.overall
        assert 0 < overall.contention <= overall.scarcity


def test_scarcity_ignores_disciplines_with_no_seats_on_offer():
    """Uma disciplina sem vaga não é oferta: entra como elegível (o aluno não a
    aprovou) mas fica fora da razão, que seria divisão por zero."""
    config = make_config(
        disciplines=[Discipline("D1", seats=6, hours=60), *[
            Discipline(f"D{i}", seats=0, hours=60) for i in range(2, 9)
        ]],
        periods=1,
    )
    result = run_simulation(config)
    overall = result.periods[0].aggregate.overall
    # Sobra uma única disciplina com vaga, disputada por todo mundo.
    assert overall.scarcity == pytest.approx(overall.students / 6)


def test_contention_does_not_move_between_rounds():
    """É grandeza do período: o conjunto pedido é a união das rodadas, então
    toda rodada mostra o mesmo valor do agregado."""
    result = run_simulation(make_config(periods=3, rounds=3))
    for period in result.periods:
        for report in period.rounds:
            assert report.overall.contention == pytest.approx(
                period.aggregate.overall.contention
            )


def test_semestralization_follows_the_entry_period_not_the_calendar():
    """Quem entra depois não é penalizado: a idade conta a partir de t_a."""
    config = make_config(periods=6)
    result = run_simulation(config)
    entry = {s.id: s.entry_period for s in generate_students(config, np.random.default_rng(config.seed))}
    hours = config.hours_by_discipline()
    for record in result.histories:
        for row in record.periods:
            age = row.period - entry[record.student_id] + 1
            assert row.approved_hours <= config.max_hours * age


def test_credits_per_seat_is_the_price_a_seat_would_fetch_if_every_credit_were_spent():
    config = make_config(periods=4)
    result = run_simulation(config)
    total_seats = sum(d.seats for d in config.disciplines)
    for period in result.periods:
        snapshots = [s for s in period.aggregate.by_course if s.active > 0]
        # Oferta do curso = por aluno x alunos; dividida pelas vagas de toda a
        # universidade dá o preço esperado, cuja soma entre cursos é global.
        for snapshot in snapshots:
            supply = snapshot.credits_per_student * snapshot.active
            assert snapshot.credits_per_seat == pytest.approx(supply / total_seats)


def test_jain_index_is_one_when_everyone_is_equally_satisfied():
    assert jain_index([0.5, 0.5, 0.5]) == pytest.approx(1.0)
    assert jain_index([1.0, 0.0, 0.0]) == pytest.approx(1 / 3)
    assert jain_index([0.0, 0.0]) == 0.0


def test_pearson_detects_perfect_correlation():
    assert pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)
    assert pearson([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]) == pytest.approx(-1.0)
    assert pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) == 0.0


def test_history_matches_the_aggregate_summary():
    """O histórico individual é a mesma simulação vista de perto: o que ele
    conta por aluno tem de bater com o resumo agregado."""
    config = make_config()
    result = run_simulation(config)
    histories = {h.student_id: h for h in result.histories}
    hours = config.hours_by_discipline()

    for summary in result.students:
        history = histories[summary.id]
        won = [
            request
            for record in history.periods
            for request in record.requests
            if request.won_round is not None
        ]
        assert summary.enrollments == len(won)
        assert summary.approvals == len({r.discipline for r in won if r.approved})
        if history.periods:
            assert summary.credits == history.periods[-1].credits_end
            assert summary.approved_hours == history.periods[-1].approved_hours
        # Quem se formou tem exatamente um período marcado com a conclusão.
        marked = [record.period for record in history.periods if record.graduated]
        assert marked == ([summary.graduated_at] if summary.graduated_at else [])
        # Carga horária obtida no período respeita W_a — eq. (14).
        for record in history.periods:
            assert record.enrolled_hours <= config.max_hours
            assert record.enrolled_hours == sum(
                hours[r.discipline] for r in record.requests if r.won_round is not None
            )


def test_history_separates_refused_requests_from_unbid_ones():
    """As três saídas de um pedido — atendido, recusado e sem lance — precisam
    aparecer distintas, que é o que a tela de depuração mostra."""
    result = run_simulation(make_config())
    requests = [r for h in result.histories for p in h.periods for r in p.requests]

    won = [r for r in requests if r.won_round is not None]
    refused = [r for r in requests if r.won_round is None and any(r.bids)]
    unbid = [r for r in requests if not any(r.bids)]
    assert won and refused and unbid, "o cenário deveria produzir as três saídas"

    for request in won:
        assert request.paid > 0 and request.attempt is not None and request.grade is not None
    for request in refused + unbid:
        assert request.paid == 0 and request.attempt is None and request.grade is None
    # Lance só sai de disciplina com utilidade positiva — eq. (18).
    assert all(r.utility > 0 for r in requests)


def test_same_seed_produces_the_same_history():
    """A tela do aluno é reconstruída re-executando a simulação, então o
    histórico precisa ser tão determinístico quanto as métricas."""
    first = run_simulation(make_config())
    second = run_simulation(make_config())
    assert first.histories == second.histories


def utilities_by_student(result) -> dict[tuple[str, int], dict[str, tuple[str, float]]]:
    """u_{a,x}^(t) como o histórico individual registrou, com o grupo da grade."""
    return {
        (history.student_id, record.period): {
            r.discipline: (r.kind, r.utility) for r in record.requests
        }
        for history in result.histories
        for record in history.periods
    }


def test_utilities_come_from_the_seed_not_from_the_simulation_path():
    """A matriz de utilidades é parâmetro de entrada: mexer num parâmetro do
    mecanismo não pode re-sortear a preferência de ninguém, senão a diferença
    entre dois cenários deixa de ser atribuível ao mecanismo.

    O sorteio é um peso por disciplina; a utilidade é esse peso normalizado
    sobre o que ainda falta cursar. Então o que tem de bater entre cenários é:
    utilidade idêntica quando o aluno chega com o mesmo conjunto elegível, e
    razão entre disciplinas do mesmo grupo sempre — a razão cancela a
    normalização e expõe o peso sorteado.
    """
    scarce = run_simulation(make_config())
    roomy = run_simulation(
        make_config(disciplines=[Discipline(f"D{i}", seats=60, hours=60) for i in range(1, 9)])
    )

    a, b = utilities_by_student(scarce), utilities_by_student(roomy)
    identical = ratios = 0
    for key in set(a) & set(b):
        if set(a[key]) == set(b[key]):
            # Mesmo conjunto elegível: nada pode diferir.
            assert a[key] == pytest.approx(
                b[key], rel=1e-9
            ), f"{key}: utilidade mudou com o número de vagas"
            identical += 1
        by_kind: dict[str, list[str]] = {}
        for name in set(a[key]) & set(b[key]):
            if a[key][name][0] == b[key][name][0]:
                by_kind.setdefault(a[key][name][0], []).append(name)
        for names in by_kind.values():
            for x, y in zip(sorted(names), sorted(names)[1:]):
                assert a[key][x][1] / a[key][y][1] == pytest.approx(
                    b[key][x][1] / b[key][y][1]
                ), f"{key}: a razão {x}/{y} mudou — o sorteio não é o mesmo"
                ratios += 1

    assert identical > 20, "deveria haver vários períodos com o mesmo conjunto elegível"
    assert ratios > 50, "a comparação deveria cobrir várias razões dentro do grupo"


def test_students_enter_in_equal_generations_one_per_period():
    """Cada curso recebe uma geração por período, todas do mesmo tamanho: o
    cenário diz quantos alunos por geração, e não um total a repartir."""
    config = make_config(periods=5)
    result = run_simulation(config)

    assert len(result.students) == config.total_students()
    for course in config.courses:
        members = [s.entry_period for s in result.students if s.course == course.name]
        counts = [members.count(period) for period in range(1, config.periods + 1)]
        assert counts == [course.students_per_generation] * config.periods

    # Ninguém aparece antes do próprio ingresso.
    by_id = {s.id: s for s in result.students}
    for history in result.histories:
        first = min((r.period for r in history.periods), default=None)
        if first is not None:
            assert first >= by_id[history.student_id].entry_period

    # Os ativos crescem enquanto as gerações vão entrando.
    active = [period.aggregate.overall.students for period in result.periods]
    assert active[0] < active[3], "os ativos deveriam crescer a cada geração"

    # O escalonamento deixou de vir da seed: é o mesmo com qualquer uma. O que
    # a seed sorteia são as pessoas, não o período em que entram.
    entries = [s.entry_period for s in result.students]
    other = run_simulation(make_config(periods=5, seed=99))
    assert entries == [s.entry_period for s in other.students]
    assert [s.name for s in result.students] != [s.name for s in other.students]


def test_every_reported_period_has_at_least_one_student():
    """Invariante dos relatórios: nenhum período é publicado sem aluno, e a
    numeração não tem buraco. Um período vazio só renderia zeros, que num
    gráfico se leem como queda e numa média puxam o valor para baixo."""
    for config in (
        make_config(),
        make_config(periods=8),
        make_config(periods=1),
    ):
        result = run_simulation(config)
        assert result.periods, "a simulação deveria publicar ao menos um período"
        assert [p.period for p in result.periods] == list(range(1, len(result.periods) + 1))
        for period in result.periods:
            assert period.aggregate.overall.students >= 1
            for report in period.rounds:
                assert report.overall.students >= 1


def test_empty_course_reports_no_metrics_instead_of_zeros():
    """Um curso sem aluno não tem métrica — tem `None`. Zero seria um ponto
    falso: 'ninguém satisfeito' em vez de 'não havia ninguém'.

    Com uma geração entrando todo período, um curso só fica vazio se não
    receber ninguém — é o cenário de `students_per_generation = 0`. O caso de
    um recorte que esvazia *depois* de ter tido gente é o das gerações, em
    `test_cohort_without_active_students_still_reports_its_graduates`.
    """
    config = SimulationConfig(
        disciplines=[Discipline(f"D{i}", seats=20, hours=60) for i in range(1, 6)],
        courses=[
            Course(
                "Vazio",
                students_per_generation=0,
                hours_to_graduate=120,
                required=("D1", "D2"),
                electives=("D3",),
            ),
            Course(
                "Cheio",
                students_per_generation=1,
                hours_to_graduate=300,
                required=("D1", "D2", "D3", "D4", "D5"),
            ),
        ],
        periods=8,
        rounds=1,
        max_hours=120,
        seed=3,
    )
    result = run_simulation(config)

    empty = [
        snapshot
        for period in result.periods
        for snapshot in period.aggregate.by_course
        if snapshot.course == "Vazio"
    ]
    assert empty, "o curso sem alunos deveria aparecer em todo período"
    for snapshot in empty:
        assert snapshot.active == 0
        assert snapshot.metrics is None
        assert snapshot.mean_credits is None
        assert snapshot.mean_approved_hours is None
        assert snapshot.credits_per_student is None
        assert snapshot.credits_per_seat is None
        assert snapshot.mean_credit_return is None
        assert snapshot.graduated == 0

    for snapshot in (
        s for p in result.periods for s in p.aggregate.by_course if s.active > 0
    ):
        assert snapshot.metrics is not None and snapshot.metrics.students == snapshot.active


def test_cohorts_partition_each_course_by_entry_period():
    """`by_cohort` é o mesmo recorte de `by_course`, só que fatiado por geração:
    somar as fatias reproduz o curso, em toda rodada e todo período."""
    result = run_simulation(make_config())
    reports = [r for p in result.periods for r in (*p.rounds, p.aggregate)]
    assert reports

    for report in reports:
        for course in report.by_course:
            assert course.entry_period is None, "o recorte do curso inteiro não tem geração"
            cohorts = [c for c in report.by_cohort if c.course == course.course]
            assert sum(c.active for c in cohorts) == course.active
            assert sum(c.graduated for c in cohorts) == course.graduated
            # uma geração só aparece uma vez por curso
            entries = [c.entry_period for c in cohorts]
            assert len(set(entries)) == len(entries)


def test_a_student_never_changes_cohort():
    """É o que distingue a geração da idade: o aluno nasce numa geração e fica
    nela até sair, então uma série sempre fala do mesmo conjunto de alunos."""
    result = run_simulation(make_config())
    entries_by_course: dict[str, set[int]] = {}
    for student in result.students:
        entries_by_course.setdefault(student.course, set()).add(student.entry_period)

    for period in result.periods:
        for cohort in period.aggregate.by_cohort:
            assert cohort.entry_period is not None
            # a geração existe no curso e já ingressou
            assert cohort.entry_period in entries_by_course[cohort.course]
            assert cohort.entry_period <= period.period
            if cohort.active:
                members = [
                    s
                    for s in result.students
                    if s.course == cohort.course and s.entry_period == cohort.entry_period
                ]
                assert cohort.active <= len(members)


def test_cohort_without_active_students_still_reports_its_graduates():
    """Uma geração que já esvaziou continua na lista enquanto tiver concluintes —
    senão a série dela sumiria justamente ao terminar de contar."""
    result = run_simulation(make_config(periods=8))
    emptied = [
        cohort
        for period in result.periods
        for cohort in period.aggregate.by_cohort
        if cohort.active == 0
    ]
    assert emptied, "neste cenário alguma geração deveria esvaziar antes do fim"
    for cohort in emptied:
        assert cohort.metrics is None
        assert cohort.mean_credits is None
        assert cohort.mean_approved_hours is None
        assert cohort.graduated > 0


def test_graduates_are_counted_in_the_cohort_they_entered():
    result = run_simulation(make_config(periods=8))
    expected: dict[tuple[str, int], int] = {}
    for student in result.students:
        if student.graduated_at is not None:
            key = (student.course, student.entry_period)
            expected[key] = expected.get(key, 0) + 1
    assert expected, "neste cenário alguém deveria se formar"

    last = result.periods[-1].aggregate
    final = {
        (c.course, c.entry_period): c.graduated
        for c in last.by_cohort
        if c.graduated and c.entry_period is not None
    }
    assert final == expected


def test_credit_return_policies_follow_their_definitions():
    """f_gamma — eq. (34). Nota de corte 5: 4,9 reprova e 5,0 aprova."""
    cases = {
        # (reprovado, aprovado raspando, aprovado com folga)
        "none": (0, 0, 0),
        "unit": (0, 1, 1),
        "full": (0, 10, 10),
        # round(4,9/10 x 10), round(5,0/10 x 10), round(9,0/10 x 10)
        "ratio": (5, 5, 9),
    }
    for policy, expected in cases.items():
        got = tuple(
            credit_return(policy, paid=10, grade=grade, min_grade=5.0)
            for grade in (4.9, 5.0, 9.0)
        )
        assert got == expected, f"política {policy}"

    # Só `ratio` devolve a quem reprovou, e nenhuma devolve mais do que o pago.
    for policy in cases:
        for grade in (0.0, 3.3, 7.7, 10.0):
            assert 0 <= credit_return(policy, paid=4, grade=grade, min_grade=5.0) <= 4

    with pytest.raises(ValueError, match="desconhecida"):
        credit_return("metade", paid=1, grade=10.0, min_grade=5.0)


def test_credit_return_is_added_to_the_budget_of_the_next_period():
    """eq. (36): C_a^(t+1,1) = C_a^(t,1) - gasto + Gamma_min + soma gamma_{a,x}.

    O histórico individual é a única tela em que essa conta aparece aberta,
    então ela tem de fechar exatamente — em todas as políticas.
    """
    for policy in ("none", "unit", "full", "ratio"):
        config = make_config(credit_return=policy)
        result = run_simulation(config)
        for history in result.histories:
            for record in history.periods:
                assert record.credits_end == (
                    record.credits_start
                    - record.credits_spent
                    + config.base_credits
                    + record.credits_returned
                )
                # O total do período é a soma do gamma de cada disciplina, e só
                # disciplina cursada devolve crédito.
                assert record.credits_returned == sum(q.returned for q in record.requests)
                assert all(q.returned == 0 for q in record.requests if q.attempt is None)


def test_each_policy_returns_what_it_promises_inside_a_full_simulation():
    """O gamma registrado por disciplina tem de bater com a política escolhida
    rodando a simulação inteira — é o que a coluna da tela do aluno mostra."""
    for policy in ("none", "unit", "full", "ratio"):
        config = make_config(credit_return=policy)
        result = run_simulation(config)
        taken = [
            request
            for history in result.histories
            for record in history.periods
            for request in record.requests
            if request.attempt is not None
        ]
        assert taken, "o cenário deveria ter disciplinas cursadas"
        for request in taken:
            assert request.returned == credit_return(
                policy,
                paid=request.paid,
                grade=request.grade,
                min_grade=config.min_grade,
            )

    # As políticas precisam se separar de fato, senão não há o que comparar.
    saldos = {
        policy: [s.credits for s in run_simulation(make_config(credit_return=policy)).students]
        for policy in ("none", "unit", "full", "ratio")
    }
    assert sum(saldos["none"]) < sum(saldos["unit"]) < sum(saldos["full"])
    assert sum(saldos["none"]) < sum(saldos["ratio"])


def test_credit_return_is_reported_only_at_the_end_of_the_period():
    """Durante as rodadas as notas ainda não saíram: o recorte por curso traz
    `None`, não 0,0 — zero ali se leria como 'a política não devolveu nada'."""
    config = make_config(credit_return="full")
    result = run_simulation(config)
    for period in result.periods:
        for report in period.rounds:
            assert all(s.mean_credit_return is None for s in report.by_course)
        for snapshot in period.aggregate.by_course:
            assert (snapshot.mean_credit_return is None) == (snapshot.active == 0)

    # E o recorte por curso é a média do que os alunos daquele curso receberam.
    entry = {h.student_id: h for h in result.histories}
    course_of = {s.id: s.course for s in result.students}
    for period in result.periods:
        for snapshot in period.aggregate.by_course:
            received = [
                record.credits_returned
                for student_id, history in entry.items()
                if course_of[student_id] == snapshot.course
                for record in history.periods
                if record.period == period.period
            ]
            if received:
                assert snapshot.mean_credit_return == pytest.approx(
                    sum(received) / len(received)
                )


def test_scenario_without_students_or_disciplines_is_rejected():
    """Garantia de que todo período tem aluno começa na entrada: um cenário sem
    ninguém não produziria período algum, e toda métrica sairia indefinida."""
    with pytest.raises(ValueError, match="pelo menos um aluno"):
        SimulationConfig(
            disciplines=[Discipline("D1", seats=5, hours=60)],
            courses=[
                Course("Curso", students_per_generation=0, hours_to_graduate=60, required=("D1",))
            ],
        )
    with pytest.raises(ValueError, match="pelo menos um aluno"):
        SimulationConfig(disciplines=[Discipline("D1", seats=5, hours=60)])
    with pytest.raises(ValueError, match="pelo menos uma disciplina"):
        SimulationConfig(courses=[Course("Curso", students_per_generation=5, hours_to_graduate=0)])


def test_entry_periods_limits_how_many_generations_enter():
    """L < |T|: só os L primeiros períodos recebem geração nova, e a população
    deixa de crescer com o horizonte."""
    config = make_config(periods=10, entry_periods=4)
    assert config.entry_span == 4
    # 3 alunos por geração (2 + 1) em 4 gerações, não em 10.
    assert config.total_students() == 12
    result = run_simulation(config)
    assert {s.entry_period for s in result.students} == {1, 2, 3, 4}


def test_entry_periods_beyond_the_horizon_is_rejected():
    with pytest.raises(ValueError, match="períodos com ingresso"):
        make_config(periods=5, entry_periods=6)


def test_without_entry_periods_every_period_receives_a_generation():
    """O default preserva o comportamento anterior: `None` = ingresso em todos
    os períodos."""
    config = make_config(periods=7)
    assert config.entry_periods is None
    assert config.entry_span == 7
    assert {s.entry_period for s in run_simulation(config).students} == set(range(1, 8))


def test_the_drain_phase_lets_late_generations_reach_the_end_of_the_course():
    """Sem fase de drenagem a última geração vive um período só e nunca se
    forma — a série por geração sairia censurada pelo horizonte, não pelo
    mecanismo. Com ela, até a última geração tem tempo de concluir."""
    censored = run_simulation(make_config(periods=8))
    last_entry = max(s.entry_period for s in censored.students)
    assert not [
        s for s in censored.students if s.entry_period == last_entry and s.graduated_at
    ]

    drained = run_simulation(make_config(periods=8, entry_periods=4))
    assert [s for s in drained.students if s.entry_period == 4 and s.graduated_at]


def test_dismissal_removes_the_student_after_the_deadline():
    config = make_config(periods=8, entry_periods=3, max_residence=3)
    result = run_simulation(config)
    dismissed = [s for s in result.students if s.dismissed_at is not None]
    assert dismissed, "ninguém foi jubilado com prazo de 3 períodos"

    for student in dismissed:
        # Permaneceu exatamente T_max períodos: nem um a mais, nem a menos.
        assert student.dismissed_at - student.entry_period + 1 == config.max_residence
        # Jubilado não se formou — as duas portas de saída são exclusivas.
        assert student.graduated_at is None

    # E não reaparece em período nenhum depois de desligado.
    by_id = {s.id: s for s in result.students}
    for history in result.histories:
        student = by_id[history.student_id]
        if student.dismissed_at is not None and history.periods:
            assert max(r.period for r in history.periods) <= student.dismissed_at


def test_graduating_on_the_last_allowed_period_beats_dismissal():
    """A conclusão (eq. 40) é decidida antes do prazo: quem fecha o curso no
    último período a que tem direito se forma, não é jubilado."""
    result = run_simulation(make_config(periods=8, entry_periods=3, max_residence=3))
    on_the_wire = [
        s
        for s in result.students
        if s.graduated_at is not None and s.graduated_at - s.entry_period + 1 == 3
    ]
    assert on_the_wire, "ninguém concluiu exatamente no prazo — teste sem objeto"
    for student in on_the_wire:
        assert student.dismissed_at is None


def test_a_deadline_closes_every_generation():
    """|T| = L - 1 + T_max: todo aluno sai por uma das duas portas antes do fim
    do horizonte, então nenhuma geração fica em aberto — é o que torna a série
    por geração comparável entre si."""
    entry_periods, max_residence = 4, 5
    result = run_simulation(
        make_config(
            periods=entry_periods - 1 + max_residence,
            entry_periods=entry_periods,
            max_residence=max_residence,
        )
    )
    for student in result.students:
        assert (student.graduated_at is None) != (student.dismissed_at is None)


def test_dismissal_frees_the_contention_of_whoever_stays():
    """O que faz o jubilamento ser modelagem e não filtro de relatório: o aluno
    sai do conjunto ativo, e um a menos disputando é menos concorrência para
    quem fica."""
    base = dict(periods=9, entry_periods=4)
    without = run_simulation(make_config(**base))
    with_deadline = run_simulation(make_config(**base, max_residence=3))

    # Os dois horizontes têm comprimentos diferentes — a corrida com prazo
    # esvazia antes —, então a comparação é no último período que ambos têm.
    common = min(len(without.periods), len(with_deadline.periods)) - 1
    thinned = with_deadline.periods[common].aggregate.overall
    full = without.periods[common].aggregate.overall
    assert thinned.students < full.students
    assert thinned.contention < full.contention


def test_population_counts_everyone_who_entered_the_cut():
    """`population` é o denominador das frações de saída: quem já ingressou no
    recorte, tenha saído ou não."""
    config = make_config(periods=8, entry_periods=3, max_residence=4)
    result = run_simulation(config)
    for period in result.periods:
        for snapshot in period.aggregate.by_course + period.aggregate.by_cohort:
            entered = [
                s
                for s in result.students
                if s.course == snapshot.course
                and snapshot.entry_period in (None, s.entry_period)
                and s.entry_period <= period.period
            ]
            assert snapshot.population == len(entered)


def test_population_is_not_the_sum_of_active_and_the_two_exits():
    """A soma ingênua conta duas vezes quem sai ao fim do período: ele disputou
    o período inteiro, então está em `active` *e* já no acumulado. Tirar a
    fração dela daria um denominador inflado."""
    result = run_simulation(make_config(periods=8, entry_periods=3, max_residence=4))
    naive = [
        (snapshot.active + snapshot.graduated + snapshot.dismissed, snapshot.population)
        for period in result.periods
        for snapshot in period.aggregate.by_course
    ]
    # Nunca menor que a população, e em algum período estritamente maior.
    assert all(total >= population for total, population in naive)
    assert any(total > population for total, population in naive)


def test_minimum_periods_to_graduate_is_the_floor_for_the_deadline():
    """ceil(S_k / W_a) do curso mais longo: nem quem nunca reprova nem perde uma
    vaga fecha o curso antes disso. Um prazo abaixo jubila todo mundo."""
    config = make_config(max_hours=180)  # S_k = 300 e 240 h
    assert config.minimum_periods_to_graduate() == 2  # ceil(300 / 180)

    doomed = run_simulation(make_config(periods=6, entry_periods=3, max_residence=1))
    assert all(s.graduated_at is None for s in doomed.students)
    assert all(s.dismissed_at is not None for s in doomed.students)


def test_zero_disables_the_deadline():
    """O jubilamento é opcional: 0 desliga a regra, e permanecer zero períodos
    não significaria nada, então o valor fica livre para servir de sentinela."""
    config = make_config(periods=8, entry_periods=3, max_residence=0)
    assert config.max_residence == 0
    result = run_simulation(config)
    assert all(s.dismissed_at is None for s in result.students)
    assert all(p.dismissed_now == 0 for p in result.periods)
    # O contraste: o mesmo cenário com prazo apertado desliga gente, então o
    # que 0 faz é desligar a regra, não escapar por sorte do cenário.
    with_deadline = run_simulation(make_config(periods=8, entry_periods=3, max_residence=2))
    assert [s for s in with_deadline.students if s.dismissed_at is not None]

    # É também o padrão: quem não configura prazo não tem jubilamento.
    assert SimulationConfig(
        disciplines=[Discipline("D1", seats=1, hours=60)],
        courses=[Course("Curso", students_per_generation=1, hours_to_graduate=60, required=("D1",))],
    ).max_residence == 0


def test_a_negative_deadline_is_rejected():
    with pytest.raises(ValueError, match="tempo máximo de permanência"):
        make_config(max_residence=-1)
