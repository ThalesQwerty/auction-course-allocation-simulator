import numpy as np
import pytest

from leilao.config import AffinityProfile, Discipline, SimulationConfig
from leilao.grading import credit_return
from leilao.metrics import demand_per_seat, jain_index, pearson, semestralization
from leilao.population import generate_students
from leilao.simulation import GUARANTEED_ROUND, run_simulation

# Grade de três períodos, duas disciplinas por período: D1 e D2 sem
# pré-requisito (a matrícula garantida de quem ingressa), D3 e D4 atrás delas,
# D5 e D6 atrás dessas. A cadeia tem três elos, então ninguém conclui em menos
# de três períodos por mais folgada que seja a oferta.
GRADE = [
    Discipline("D1", seats=6, hours=60),
    Discipline("D2", seats=6, hours=60),
    Discipline("D3", seats=6, hours=60, prerequisites=("D1",)),
    Discipline("D4", seats=6, hours=60, prerequisites=("D2",)),
    Discipline("D5", seats=6, hours=60, prerequisites=("D3",)),
    Discipline("D6", seats=6, hours=60, prerequisites=("D3", "D4")),
]


# W_a é do perfil de afinidade: 180 h deixa o aluno cursar três disciplinas de
# 60 h por período, que é o aperto que os testes de escassez pressupõem.
WORKLOAD = 180
NEUTRAL = AffinityProfile("Padrão", "concentrated", 1, WORKLOAD, 100)


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=5,
        students_per_period=3,
        rounds=2,
        affinity_profiles=[NEUTRAL],
        seed=11,
    )
    return SimulationConfig(**{**base, **overrides})


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
            assert snapshot.granted <= snapshot.filled


def test_students_never_exceed_the_period_workload():
    config = make_config()
    result = run_simulation(config)
    hours = config.hours_by_discipline()
    max_disciplines = WORKLOAD // min(hours.values())
    for period in result.periods:
        for snapshot in period.aggregate.by_cohort:
            if snapshot.metrics:
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
    assert last.aggregate.overall.active < entered

    # E ninguém reaparece depois de concluir.
    by_id = {s.id: s for s in result.students}
    for history in result.histories:
        student = by_id[history.student_id]
        if student.graduated_at is not None and history.periods:
            assert max(r.period for r in history.periods) <= student.graduated_at


def test_graduating_means_approving_the_whole_curriculum():
    """Toda disciplina é obrigatória: concluir é aprovar em todas, e a carga
    aprovada do concluinte é a grade inteira."""
    config = make_config(periods=12)
    result = run_simulation(config)
    total_hours = config.hours_to_graduate()
    done = [s for s in result.students if s.graduated_at is not None]
    assert done, "ninguém concluiu o curso"
    for student in done:
        assert student.approved_hours == total_hours
        assert student.approvals == len(config.disciplines)
    # E quem não concluiu não aprovou tudo — senão a eq. (40) teria falhado.
    for student in result.students:
        if student.graduated_at is None:
            assert student.approvals < len(config.disciplines)


def test_nobody_graduates_faster_than_the_prerequisite_chain():
    """A cadeia impõe um piso que a oferta não compra: a disciplina do n-ésimo
    período da grade não pode ser cursada antes do n-ésimo período do aluno."""
    config = make_config(periods=12, disciplines=[
        Discipline(d.name, seats=200, hours=d.hours, prerequisites=d.prerequisites)
        for d in GRADE
    ])
    assert config.minimum_periods_to_graduate() == 3  # três elos
    result = run_simulation(config)
    for student in result.students:
        if student.graduated_at is not None:
            assert student.graduated_at - student.entry_period + 1 >= 3


def test_metrics_stay_within_their_theoretical_ranges():
    result = run_simulation(make_config())
    for period in result.periods:
        for report in [*period.rounds, period.aggregate]:
            groups = [report.overall, *report.by_cohort]
            for metrics in [g.metrics for g in groups if g.metrics]:
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
                parts = [c for c in report.by_cohort if c.metrics]
                total = sum(getattr(c.metrics, field) * c.metrics.students for c in parts)
                assert total / report.overall.metrics.students == pytest.approx(
                    getattr(report.overall.metrics, field)
                )


def test_scarcity_only_counts_who_can_actually_take_the_discipline():
    """No primeiro período ninguém aprovou nada: só as disciplinas sem
    pré-requisito são elegíveis, e cada uma tem a população inteira disputando
    as suas vagas. As demais não entram na conta de ninguém."""
    config = make_config(periods=1)
    result = run_simulation(config)
    overall = result.periods[0].aggregate.overall.metrics
    first = config.first_period_disciplines()
    seats = config.hours_by_discipline()  # só para ter o dict de nomes
    assert set(first) == {"D1", "D2"}
    by_name = {d.name: d for d in config.disciplines}
    expected = sum(overall.students / by_name[name].seats for name in first) / len(first)
    assert overall.scarcity == pytest.approx(expected)
    assert seats.keys() == by_name.keys()


def test_scarcity_measures_potential_demand_and_contention_the_realized_one():
    """O par: só se pede o que é elegível, então a demanda que se materializa é
    uma fração da potencial — e é a razão entre as duas que diz quanta."""
    result = run_simulation(make_config(periods=6))
    for period in result.periods:
        overall = period.aggregate.overall.metrics
        assert 0 < overall.contention <= overall.scarcity


def test_scarcity_ignores_disciplines_with_no_seats_on_offer():
    """Uma disciplina sem vaga não é oferta: entra como elegível (o aluno não a
    aprovou) mas fica fora da razão, que seria divisão por zero."""
    config = make_config(
        disciplines=[
            Discipline("D1", seats=6, hours=60),
            # Sem vaga, mas elegíveis assim que D1 sair: ficam fora da razão.
            Discipline("D2", seats=0, hours=60, prerequisites=("D1",)),
            Discipline("D3", seats=0, hours=60, prerequisites=("D1",)),
        ],
        periods=1,
    )
    result = run_simulation(config)
    overall = result.periods[0].aggregate.overall.metrics
    # Sobra uma única disciplina com vaga, disputada por todo mundo.
    assert overall.scarcity == pytest.approx(overall.students / 6)


def test_contention_does_not_move_between_rounds():
    """É grandeza do período: o conjunto pedido é a união das rodadas, então
    toda rodada mostra o mesmo valor do agregado."""
    result = run_simulation(make_config(periods=3, rounds=3))
    for period in result.periods:
        for report in period.rounds:
            assert report.overall.metrics.contention == pytest.approx(
                period.aggregate.overall.metrics.contention
            )


def test_semestralization_follows_the_entry_period_not_the_calendar():
    """Quem entra depois não é penalizado: a idade conta a partir de t_a."""
    config = make_config(periods=6)
    result = run_simulation(config)
    entry = {s.id: s.entry_period for s in generate_students(config, np.random.default_rng(config.seed))}
    for record in result.histories:
        for row in record.periods:
            age = row.period - entry[record.student_id] + 1
            assert row.approved_hours <= WORKLOAD * age


def test_credits_per_seat_is_the_price_a_seat_would_fetch_if_every_credit_were_spent():
    config = make_config(periods=4)
    result = run_simulation(config)
    total_seats = sum(d.seats for d in config.disciplines)
    for period in result.periods:
        for snapshot in period.aggregate.by_cohort:
            if snapshot.active == 0:
                continue
            # Oferta da geração = por aluno x alunos; dividida pelas vagas de
            # toda a universidade dá o preço esperado, cuja soma é global.
            supply = snapshot.credits_per_student * snapshot.active
            assert snapshot.credits_per_seat == pytest.approx(supply / total_seats)
        cohorts = [c.credits_per_seat for c in period.aggregate.by_cohort if c.active]
        assert period.aggregate.overall.credits_per_seat == pytest.approx(sum(cohorts))


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
            assert record.enrolled_hours <= WORKLOAD
            assert record.enrolled_hours == sum(
                hours[r.discipline] for r in record.requests if r.won_round is not None
            )


def test_history_separates_refused_requests_from_unbid_ones():
    """As saídas de um pedido — atendido, recusado e sem lance — precisam
    aparecer distintas, que é o que a tela de depuração mostra.

    Cenário montado para produzir as três: D1 tem exatamente as vagas de uma
    geração, então os ingressantes a esgotam e quem precisa recursá-la não
    encontra oferta — é o "sem lance". D3, com uma vaga só, produz o
    "recusada".
    """
    result = run_simulation(
        make_config(
            periods=8,
            disciplines=[
                Discipline("D1", seats=3, hours=60),
                Discipline("D2", seats=6, hours=60),
                Discipline("D3", seats=1, hours=60, prerequisites=("D1",)),
                Discipline("D4", seats=6, hours=60, prerequisites=("D2",)),
            ],
        )
    )
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


def utilities_by_student(result) -> dict[tuple[str, int], dict[str, float]]:
    """u_{a,x}^(t) como o histórico individual registrou."""
    return {
        (history.student_id, record.period): {
            r.discipline: r.utility for r in record.requests
        }
        for history in result.histories
        for record in history.periods
    }


def test_utilities_come_from_the_seed_not_from_the_simulation_path():
    """A matriz de utilidades é parâmetro de entrada: mexer num parâmetro do
    mecanismo não pode re-sortear a preferência de ninguém, senão a diferença
    entre dois cenários deixa de ser atribuível ao mecanismo.

    O sorteio é um peso por disciplina; a utilidade é esse peso normalizado
    sobre o conjunto elegível. Então o que tem de bater entre cenários é:
    utilidade idêntica quando o aluno chega com o mesmo conjunto elegível, e
    razão entre duas disciplinas quaisquer sempre — a razão cancela a
    normalização e expõe o peso sorteado.
    """
    scarce = run_simulation(make_config())
    roomy = run_simulation(
        make_config(
            disciplines=[
                Discipline(d.name, seats=60, hours=d.hours, prerequisites=d.prerequisites)
                for d in GRADE
            ]
        )
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
        shared = sorted(set(a[key]) & set(b[key]))
        for x, y in zip(shared, shared[1:]):
            assert a[key][x] / a[key][y] == pytest.approx(
                b[key][x] / b[key][y]
            ), f"{key}: a razão {x}/{y} mudou — o sorteio não é o mesmo"
            ratios += 1

    assert identical > 20, "deveria haver vários períodos com o mesmo conjunto elegível"
    assert ratios > 20, "a comparação deveria cobrir várias razões"


def test_students_enter_in_equal_generations_one_per_period():
    """Entra uma geração por período, todas do mesmo tamanho: o cenário diz
    quantos alunos por período, e não um total a repartir."""
    config = make_config(periods=5)
    result = run_simulation(config)

    assert len(result.students) == config.total_students()
    entries = [s.entry_period for s in result.students]
    counts = [entries.count(period) for period in range(1, config.periods + 1)]
    assert counts == [config.students_per_period] * config.periods

    # Ninguém aparece antes do próprio ingresso.
    by_id = {s.id: s for s in result.students}
    for history in result.histories:
        first = min((r.period for r in history.periods), default=None)
        if first is not None:
            assert first >= by_id[history.student_id].entry_period

    # Os ativos crescem enquanto as gerações vão entrando.
    active = [period.aggregate.overall.active for period in result.periods]
    assert active[0] < active[3], "os ativos deveriam crescer a cada geração"

    # O escalonamento não vem da seed: é o mesmo com qualquer uma. O que a seed
    # sorteia são as pessoas, não o período em que entram.
    other = run_simulation(make_config(periods=5, seed=99))
    assert entries == [s.entry_period for s in other.students]
    assert [s.name for s in result.students] != [s.name for s in other.students]


def test_every_reported_period_has_at_least_one_student():
    """Invariante dos relatórios: nenhum período é publicado sem aluno, e a
    numeração não tem buraco. Um período vazio só renderia zeros, que num
    gráfico se leem como queda e numa média puxam o valor para baixo."""
    for config in (make_config(), make_config(periods=8), make_config(periods=1)):
        result = run_simulation(config)
        assert result.periods, "a simulação deveria publicar ao menos um período"
        assert [p.period for p in result.periods] == list(range(1, len(result.periods) + 1))
        for period in result.periods:
            assert period.aggregate.overall.metrics.students >= 1
            for report in period.rounds:
                assert report.overall.metrics.students >= 1


# --- matrícula garantida de quem ingressa ---------------------------------


def first_period_records(result, students):
    """O registro do período de ingresso de cada aluno."""
    entry = {s.id: s.entry_period for s in students}
    return [
        (history.student_id, record)
        for history in result.histories
        for record in history.periods
        if record.period == entry[history.student_id]
    ]


def test_entrants_get_every_first_period_discipline_without_bidding():
    config = make_config(periods=6)
    result = run_simulation(config)
    first = set(config.first_period_disciplines())
    assert first == {"D1", "D2"}

    records = first_period_records(result, result.students)
    assert records, "toda geração deveria ter um período de ingresso registrado"
    for student_id, record in records:
        granted = {r.discipline for r in record.requests if r.won_round == GUARANTEED_ROUND}
        assert granted == first, f"{student_id} não recebeu a matrícula garantida inteira"
        # Nada mais é elegível para quem acabou de entrar, então o pedido é
        # exatamente a matrícula garantida.
        assert {r.discipline for r in record.requests} == first
        # E a satisfação é plena: ele obteve tudo que podia querer — eq. (51).
        assert record.satisfaction == pytest.approx(1.0)


def test_the_system_charges_the_entrant_an_equal_share_of_the_budget():
    """"Gastaram seus créditos igualmente", com o resto da divisão no saldo."""
    config = make_config(periods=4, base_credits=10)
    result = run_simulation(config)
    first = config.first_period_disciplines()
    share = config.base_credits // len(first)  # 10 // 2 = 5

    for _, record in first_period_records(result, result.students):
        assert record.credits_start == config.base_credits
        assert all(r.paid == share for r in record.requests)
        assert record.credits_spent == share * len(first)
        # O remanescente continua no saldo, somado ao Gamma_min do período.
        remainder = config.base_credits - share * len(first)
        assert record.credits_end == remainder + config.base_credits + record.credits_returned


def test_an_indivisible_budget_leaves_the_remainder_with_the_entrant():
    """Divisão inteira: com 7 créditos e 2 disciplinas, 3 em cada e 1 de sobra."""
    config = make_config(periods=2, base_credits=7)
    result = run_simulation(config)
    for _, record in first_period_records(result, result.students):
        assert record.credits_spent == 6
        assert record.credits_end == 1 + 7 + record.credits_returned


def test_the_entrant_share_feeds_the_credit_return():
    """O que a matrícula garantida entrega ao f_gamma da eq. (34): o valor
    lançado é o `paid` da disciplina, e é sobre ele que a política trabalha."""
    config = make_config(periods=4, credit_return="full", base_credits=10)
    result = run_simulation(config)
    share = config.base_credits // len(config.first_period_disciplines())
    returned = [
        r
        for _, record in first_period_records(result, result.students)
        for r in record.requests
        if r.approved
    ]
    assert returned, "alguém deveria aprovar na matrícula garantida"
    assert all(r.returned == share for r in returned)


def test_guaranteed_seats_leave_the_market_before_the_first_round():
    """A vaga entregue ao ingressante não é ofertada: ela já saiu do estoque
    quando a primeira rodada abre, e é isso que a coluna `granted` mostra."""
    config = make_config(periods=5)
    result = run_simulation(config)
    first = set(config.first_period_disciplines())
    per_period = config.students_per_period

    for period in result.periods:
        for snapshot in period.disciplines:
            if snapshot.name in first and period.period <= config.entry_span:
                assert snapshot.granted == per_period
            else:
                assert snapshot.granted == 0


def test_a_generation_larger_than_the_smallest_first_period_offer_is_rejected():
    """A garantia só é garantia se couber: o ritmo de ingresso não pode passar
    da menor oferta entre as disciplinas de 1º período."""
    with pytest.raises(ValueError, match="menor oferta"):
        SimulationConfig(
            disciplines=[
                Discipline("D1", seats=5, hours=60),
                Discipline("D2", seats=3, hours=60),
            ],
            students_per_period=4,
        )
    # Exatamente no teto passa — e não sobra vaga nenhuma para quem recursa.
    assert SimulationConfig(
        disciplines=[Discipline("D1", seats=4, hours=60), Discipline("D2", seats=4, hours=60)],
        students_per_period=4,
    ).students_per_period == 4


def test_a_first_period_heavier_than_the_workload_cap_is_rejected():
    """O ingressante cursa as de 1º período todas de uma vez: a carga somada
    delas tem de caber em W_a, senão a eq. (4) seria violada na entrada."""
    with pytest.raises(ValueError, match="não cabem na carga horária máxima"):
        SimulationConfig(
            disciplines=[
                Discipline("D1", seats=5, hours=60),
                Discipline("D2", seats=5, hours=60),
            ],
            students_per_period=2,
            affinity_profiles=[AffinityProfile("Apertado", "concentrated", 1, 100, 100)],
        )


def test_retaking_a_first_period_discipline_goes_through_the_auction():
    """A garantia vale só no ingresso: quem reprova em D1 disputa a vaga como
    qualquer outro, no leilão."""
    config = make_config(periods=8)
    result = run_simulation(config)
    first = set(config.first_period_disciplines())
    entry = {s.id: s.entry_period for s in result.students}

    retakes = [
        r
        for history in result.histories
        for record in history.periods
        if record.period > entry[history.student_id]
        for r in record.requests
        if r.discipline in first
    ]
    assert retakes, "alguém deveria reprovar numa disciplina de 1º período"
    assert all(r.won_round != GUARANTEED_ROUND for r in retakes)


# --- recorte por geração ---------------------------------------------------


def test_cohorts_partition_the_university():
    """`by_cohort` é o mesmo recorte de `overall`, fatiado por geração: somar as
    fatias reproduz a universidade, em toda rodada e todo período."""
    result = run_simulation(make_config())
    reports = [r for p in result.periods for r in (*p.rounds, p.aggregate)]
    assert reports

    for report in reports:
        assert report.overall.group is None, "o agregado não tem geração"
        assert sum(c.active for c in report.by_cohort) == report.overall.active
        assert sum(c.graduated for c in report.by_cohort) == report.overall.graduated
        assert sum(c.population for c in report.by_cohort) == report.overall.population
        # uma geração só aparece uma vez
        entries = [c.group for c in report.by_cohort]
        assert len(set(entries)) == len(entries)
        assert all(entry is not None for entry in entries)


def test_a_student_never_changes_cohort():
    """É o que distingue a geração da idade: o aluno nasce numa geração e fica
    nela até sair, então uma série sempre fala do mesmo conjunto de alunos."""
    result = run_simulation(make_config())
    entries = {s.entry_period for s in result.students}

    for period in result.periods:
        for cohort in period.aggregate.by_cohort:
            entry = int(cohort.group)
            assert entry in entries
            assert entry <= period.period
            members = [s for s in result.students if s.entry_period == entry]
            assert cohort.population == len(members)
            assert cohort.active <= len(members)


def test_an_emptied_cohort_stays_in_the_series_with_its_graduates():
    """Uma geração que já esvaziou continua na lista enquanto a simulação
    correr — senão a série dela sumiria justamente ao terminar de contar."""
    result = run_simulation(make_config(periods=10, entry_periods=2))
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
    result = run_simulation(make_config(periods=10))
    expected: dict[int, int] = {}
    for student in result.students:
        if student.graduated_at is not None:
            expected[student.entry_period] = expected.get(student.entry_period, 0) + 1
    assert expected, "neste cenário alguém deveria se formar"

    final = {
        int(c.group): c.graduated
        for c in result.periods[-1].aggregate.by_cohort
        if c.graduated
    }
    assert final == expected


# --- retorno de créditos ---------------------------------------------------


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
    então ela tem de fechar exatamente — em todas as políticas, inclusive no
    período de ingresso, em que o gasto é o que o sistema lançou.
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
    """Durante as rodadas as notas ainda não saíram: o recorte traz `None`, não
    0,0 — zero ali se leria como 'a política não devolveu nada'."""
    config = make_config(credit_return="full")
    result = run_simulation(config)
    for period in result.periods:
        for report in period.rounds:
            assert report.overall.mean_credit_return is None
            assert all(c.mean_credit_return is None for c in report.by_cohort)
        for snapshot in period.aggregate.by_cohort:
            assert (snapshot.mean_credit_return is None) == (snapshot.active == 0)

    # E o recorte é a média do que os alunos daquela geração receberam.
    entry_of = {s.id: s.entry_period for s in result.students}
    for period in result.periods:
        for snapshot in period.aggregate.by_cohort:
            received = [
                record.credits_returned
                for history in result.histories
                if entry_of[history.student_id] == int(snapshot.group)
                for record in history.periods
                if record.period == period.period
            ]
            if received:
                assert snapshot.mean_credit_return == pytest.approx(
                    sum(received) / len(received)
                )


# --- validação do cenário --------------------------------------------------


def test_scenario_without_students_or_disciplines_is_rejected():
    """Garantia de que todo período tem aluno começa na entrada: um cenário sem
    ninguém não produziria período algum, e toda métrica sairia indefinida."""
    with pytest.raises(ValueError, match="pelo menos um aluno"):
        SimulationConfig(
            disciplines=[Discipline("D1", seats=5, hours=60)], students_per_period=0
        )
    with pytest.raises(ValueError, match="pelo menos uma disciplina"):
        SimulationConfig(students_per_period=5)


def test_entry_periods_limits_how_many_generations_enter():
    """L < |T|: só os L primeiros períodos recebem geração nova, e a população
    deixa de crescer com o horizonte."""
    config = make_config(periods=10, entry_periods=4)
    assert config.entry_span == 4
    assert config.total_students() == 12  # 3 por geração em 4 gerações
    result = run_simulation(config)
    assert {s.entry_period for s in result.students} == {1, 2, 3, 4}


def test_entry_periods_beyond_the_horizon_is_rejected():
    with pytest.raises(ValueError, match="períodos com ingresso"):
        make_config(periods=5, entry_periods=6)


def test_without_entry_periods_every_period_receives_a_generation():
    """O default: `None` = ingresso em todos os períodos."""
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






def test_population_counts_everyone_who_entered_the_cut():
    """`population` é o denominador da fração de formados: quem já ingressou no
    recorte, tenha concluído ou não."""
    config = make_config(periods=8, entry_periods=3)
    result = run_simulation(config)
    for period in result.periods:
        for snapshot in [period.aggregate.overall, *period.aggregate.by_cohort]:
            entered = [
                s
                for s in result.students
                if snapshot.group in (None, str(s.entry_period))
                and s.entry_period <= period.period
            ]
            assert snapshot.population == len(entered)


def test_population_is_not_active_plus_graduated():
    """A soma ingênua conta duas vezes quem se forma ao fim do período: ele
    disputou o período inteiro, então está em `active` *e* já no acumulado.
    Tirar a fração dela daria um denominador inflado."""
    result = run_simulation(make_config(periods=8, entry_periods=3))
    naive = [
        (snapshot.active + snapshot.graduated, snapshot.population)
        for period in result.periods
        for snapshot in period.aggregate.by_cohort
    ]
    # Nunca menor que a população, e em algum período estritamente maior.
    assert all(total >= population for total, population in naive)
    assert any(total > population for total, population in naive)


def test_minimum_periods_to_graduate_takes_the_tighter_of_the_two_limits():
    """São dois pisos — a carga horária e a cadeia de pré-requisitos — e vale o
    maior. Um prazo abaixo dele jubila todo mundo."""
    # Grade de 360 h em 3 elos: com W_a = 180 a carga pede 2 e a cadeia pede 3,
    # então manda a cadeia.
    config = make_config()
    assert config.hours_to_graduate() == 360
    assert config.minimum_periods_to_graduate() == 3  # max(ceil(360/180), 3)

    # Grade rasa e larga: 2 elos só, mas 300 h que não cabem num período. Aqui
    # manda a carga horária.
    wide = SimulationConfig(
        disciplines=[
            Discipline("A", seats=5, hours=60),
            *[
                Discipline(name, seats=5, hours=60, prerequisites=("A",))
                for name in ("B", "C", "D", "E")
            ],
        ],
        students_per_period=5,
        affinity_profiles=[AffinityProfile("Estreito", "concentrated", 1, 60, 100)],
    )
    assert wide.hours_to_graduate() == 300
    assert max(wide.curriculum_periods().values()) == 2
    assert wide.minimum_periods_to_graduate() == 5  # max(ceil(300/60), 2)

    # Horizonte abaixo do piso: ninguém chega ao fim, por construção.
    doomed = run_simulation(make_config(periods=2, entry_periods=1))
    assert all(s.graduated_at is None for s in doomed.students)




