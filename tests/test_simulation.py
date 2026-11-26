import numpy as np
import pytest

from profiles import single_axis
from disciplines import disciplines_from_predecessors
from leilao.config import Discipline, SimulationConfig, horizon_for_window
from leilao.equations import next_budget, progress
from leilao.grading import credit_return
from leilao.metrics import demand_per_seat, jain_index, semestralization
from leilao.population import generate_students
from leilao.simulation import GUARANTEED_ROUND, run_simulation

GRADE = disciplines_from_predecessors(
    ("D1", 6, 60),
    ("D2", 6, 60),
    ("D3", 6, 60, ("D1",)),
    ("D4", 6, 60, ("D2",)),
    ("D5", 6, 60, ("D3",)),
    ("D6", 6, 60, ("D3", "D4")),
)


WORKLOAD = 180

NEVER_APPROVES = dict(
    periods=2,
    approval_rate=1e-9,
)


def make_config(**overrides) -> SimulationConfig:
    base = dict(
        disciplines=GRADE,
        periods=5,
        students_per_entry_class=3,
        rounds=2,
        max_hours=WORKLOAD,
        **single_axis(WORKLOAD),
        seed=11,
    )
    return SimulationConfig(**{**base, **overrides})


def test_same_seed_produces_the_same_simulation():
    first = run_simulation(make_config())
    second = run_simulation(make_config())
    assert [s.grade_average for s in first.students] == [s.grade_average for s in second.students]
    assert [s.graduated_at for s in first.students] == [s.graduated_at for s in second.students]
    assert first.periods[-1].aggregate.overall == second.periods[-1].aggregate.overall


@pytest.mark.parametrize("mechanism", ["credits", "ranking"])
def test_dropping_the_history_changes_nothing_but_the_history(mechanism):
    """`histories="nenhum"` é economia de memória, não outro cenário."""
    config = make_config(mechanism=mechanism)
    full = run_simulation(config)
    lean = run_simulation(config, histories="nenhum")

    assert lean.histories == []
    assert full.histories != []
    assert lean.periods == full.periods
    assert lean.students == full.students
    assert lean.interest_distribution == full.interest_distribution
    assert lean.grade_distribution == full.grade_distribution


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

    last = result.periods[-1]
    entered = len([s for s in result.students if s.entry_period <= last.period])
    assert last.aggregate.overall.active < entered

    by_id = {s.id: s for s in result.students}
    for history in result.histories:
        student = by_id[history.student_id]
        if student.graduated_at is not None and history.periods:
            assert max(r.period for r in history.periods) <= student.graduated_at


def test_graduating_means_approving_the_whole_curriculum():
    """Toda disciplina é obrigatória: concluir é aprovar em todas, e a carga"""
    config = make_config(periods=12)
    result = run_simulation(config)
    total_hours = config.hours_to_graduate()
    done = [s for s in result.students if s.graduated_at is not None]
    assert done, "ninguém concluiu o curso"
    for student in done:
        assert student.approved_hours == total_hours
        assert student.approvals == len(config.disciplines)
    for student in result.students:
        if student.graduated_at is None:
            assert student.approvals < len(config.disciplines)


def test_nobody_graduates_faster_than_the_prerequisite_chain():
    """A cadeia impõe um piso que a oferta não compra: a disciplina do n-ésimo"""
    config = make_config(periods=12, disciplines=[
        Discipline(d.name, seats=200, hours=d.hours, unlocks=d.unlocks, entry=d.entry)
        for d in GRADE
    ])
    assert config.minimum_periods_to_graduate() == 3
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
                assert 0 <= metrics.satisfaction <= 1
                assert 0 <= metrics.fairness <= 1
                assert metrics.scarcity >= 0
                assert metrics.contention >= 0
                assert 0 <= metrics.semestralization <= 1


def test_semestralization_is_zero_in_the_entry_period_and_one_at_full_load():
    assert semestralization(approved_hours=0, max_hours=120, periods_completed=0) == 0.0
    assert semestralization(approved_hours=240, max_hours=120, periods_completed=2) == 1.0
    assert semestralization(approved_hours=120, max_hours=120, periods_completed=2) == 0.5


def test_demand_per_seat_is_the_mean_candidate_per_seat_ratio():
    assert demand_per_seat(demands=[2 / 10, 4 / 10]) == pytest.approx(0.3)
    assert demand_per_seat(demands=[]) == 0.0


def test_demand_per_seat_sees_who_else_wants_the_same_seats():
    """O que uma medida do *tamanho* da oferta não veria. Dois alunos diante de"""
    separate = [demand_per_seat(demands=[1 / 60]), demand_per_seat(demands=[1 / 60])]
    together = [demand_per_seat(demands=[2 / 60]), demand_per_seat(demands=[2 / 60])]
    assert sum(together) / len(together) == 2 * (sum(separate) / len(separate))


def test_scarcity_and_contention_are_means_over_students_not_sums():
    """Médias: a contagem de quem quer já traz a população dentro do valor de"""
    result = run_simulation(make_config(periods=4))
    for period in result.periods:
        for report in [*period.rounds, period.aggregate]:
            if report.overall.metrics is None:
                continue
            for field in ("scarcity", "contention"):
                parts = [c for c in report.by_cohort if c.metrics]
                total = sum(getattr(c.metrics, field) * c.metrics.students for c in parts)
                assert total / report.overall.metrics.students == pytest.approx(
                    getattr(report.overall.metrics, field)
                )


def test_scarcity_only_counts_who_can_actually_take_the_discipline():
    """Enquanto ninguém aprovou nada, só as disciplinas sem pré-requisito são"""
    config = make_config(**NEVER_APPROVES)
    result = run_simulation(config)
    snapshot = result.periods[1].aggregate.overall
    overall = snapshot.metrics
    first = config.entry_disciplines()
    seats = config.hours_by_discipline()
    assert set(first) == {"D1", "D2"}
    by_name = {d.name: d for d in config.disciplines}
    expected = sum(snapshot.active / by_name[name].seats for name in first) / len(first)
    assert overall.scarcity == pytest.approx(expected)
    assert seats.keys() == by_name.keys()


def test_scarcity_measures_potential_demand_and_contention_the_realized_one():
    """O par: só se pede o que é elegível, então a demanda que se materializa é"""
    result = run_simulation(make_config(periods=6))
    measured = 0
    for period in result.periods:
        overall = period.aggregate.overall.metrics
        if overall is None:
            continue
        measured += 1
        assert 0 < overall.contention <= overall.scarcity
    assert measured, "nenhum período trouxe métrica para conferir"


def test_scarcity_ignores_disciplines_with_no_seats_on_offer():
    """Uma disciplina sem vaga não é oferta: entra como elegível (o aluno não a"""
    config = make_config(
        disciplines=[
            *disciplines_from_predecessors(
                ("D1", 6, 60),
                ("D2", 0, 60, ("D1",)),
                ("D3", 0, 60, ("D1",)),
            ),
        ],
        **NEVER_APPROVES,
    )
    result = run_simulation(config)
    snapshot = result.periods[1].aggregate.overall
    assert snapshot.metrics.scarcity == pytest.approx(snapshot.active / 6)


def test_contention_does_not_move_between_rounds():
    """É grandeza do período: o conjunto pedido é a união das rodadas, então"""
    result = run_simulation(make_config(periods=3, rounds=3))
    for period in result.periods:
        if period.aggregate.overall.metrics is None:
            continue
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
        if period.aggregate.overall.credits_per_seat is None:
            continue
        for snapshot in period.aggregate.by_cohort:
            if snapshot.metrics is None:
                continue
            supply = snapshot.credits_per_student * snapshot.metrics.students
            assert snapshot.credits_per_seat == pytest.approx(supply / total_seats)
        cohorts = [
            c.credits_per_seat for c in period.aggregate.by_cohort if c.metrics
        ]
        assert period.aggregate.overall.credits_per_seat == pytest.approx(sum(cohorts))


def test_jain_index_is_one_when_everyone_is_equally_satisfied():
    assert jain_index([0.5, 0.5, 0.5]) == pytest.approx(1.0)
    assert jain_index([1.0, 0.0, 0.0]) == pytest.approx(1 / 3)
    assert jain_index([0.0, 0.0]) == 0.0


def test_history_matches_the_aggregate_summary():
    """O histórico individual é a mesma simulação vista de perto: o que ele"""
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
        assert summary.enrollments == len([r for r in won if not r.excluded])
        assert summary.approvals == len({r.discipline for r in won if r.approved})
        if history.periods:
            assert summary.credits == history.periods[-1].credits_end
            assert summary.approved_hours == history.periods[-1].approved_hours
        marked = [record.period for record in history.periods if record.graduated]
        assert marked == ([summary.graduated_at] if summary.graduated_at else [])
        for record in history.periods:
            assert record.enrolled_hours <= WORKLOAD
            assert record.enrolled_hours == sum(
                hours[r.discipline] for r in record.requests if r.won_round is not None
            )
            assert record.retained_hours == sum(
                hours[r.discipline]
                for r in record.requests
                if r.won_round is not None and not r.excluded
            )
            assert record.retained_hours <= record.effective_load


def test_history_separates_refused_requests_from_unbid_ones():
    """As saídas de um pedido — atendido, recusado e sem lance — precisam"""
    result = run_simulation(
        make_config(
            periods=8,
            disciplines=[
                *disciplines_from_predecessors(
                    ("D1", 3, 60),
                    ("D2", 6, 60),
                    ("D3", 1, 60, ("D1",)),
                    ("D4", 6, 60, ("D2",)),
                ),
            ],
        )
    )
    requests = [r for h in result.histories for p in h.periods for r in p.requests]

    won = [r for r in requests if r.won_round is not None]
    coursed = [r for r in won if not r.excluded]
    excluded = [r for r in won if r.excluded]
    refused = [r for r in requests if r.won_round is None and any(r.bids)]
    unbid = [r for r in requests if not any(r.bids)]
    assert coursed and refused and unbid, "o cenário deveria produzir as saídas"

    for request in coursed:
        assert request.paid > 0 and request.attempt is not None and request.grade is not None
    for request in excluded:
        assert request.paid > 0 and request.attempt is None and request.grade is None
    for request in refused + unbid:
        assert request.paid == 0 and request.attempt is None and request.grade is None
        assert not request.excluded
    assert all(r.utility > 0 for r in requests)


def test_same_seed_produces_the_same_history():
    """A tela do aluno é reconstruída re-executando a simulação, então o"""
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
    """O interesse é parâmetro de entrada: mexer num parâmetro do mecanismo"""
    scarce = run_simulation(make_config())
    roomy = run_simulation(
        make_config(
            disciplines=[
                Discipline(d.name, seats=60, hours=d.hours, unlocks=d.unlocks, entry=d.entry)
                for d in GRADE
            ]
        )
    )

    a, b = utilities_by_student(scarce), utilities_by_student(roomy)
    identical = ratios = 0
    for key in set(a) & set(b):
        if set(a[key]) == set(b[key]):
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
    """Entra uma geração por período, todas do mesmo tamanho: o cenário diz"""
    config = make_config(periods=5)
    result = run_simulation(config)

    assert len(result.students) == config.total_students()
    entries = [s.entry_period for s in result.students]
    counts = [entries.count(period) for period in range(1, config.periods + 1)]
    assert counts == [config.students_per_period] * config.periods

    by_id = {s.id: s for s in result.students}
    for history in result.histories:
        first = min((r.period for r in history.periods), default=None)
        if first is not None:
            assert first >= by_id[history.student_id].entry_period

    active = [period.aggregate.overall.active for period in result.periods]
    assert active[0] < active[3], "os ativos deveriam crescer a cada geração"

    other = run_simulation(make_config(periods=5, seed=99))
    assert entries == [s.entry_period for s in other.students]
    assert [s.name for s in result.students] != [s.name for s in other.students]


def test_every_reported_period_has_at_least_one_student():
    """Invariante dos relatórios: nenhum período é publicado sem aluno, e a"""
    for config in (make_config(), make_config(periods=8), make_config(periods=1)):
        result = run_simulation(config)
        assert result.periods, "a simulação deveria publicar ao menos um período"
        assert [p.period for p in result.periods] == list(range(1, len(result.periods) + 1))
        for period in result.periods:
            for report in [*period.rounds, period.aggregate]:
                assert report.overall.active >= 1
                if report.overall.metrics is None:
                    continue
                assert report.overall.metrics.students >= 1
                assert report.overall.metrics.students <= report.overall.active


def test_the_entering_generation_is_left_out_of_the_metrics():
    """O calouro não disputou nada: recebeu vaga garantida em tudo que lhe era"""
    config = make_config(periods=4)
    result = run_simulation(config)
    entry = {s.id: s.entry_period for s in result.students}

    first = result.periods[0].aggregate
    assert first.overall.active == config.students_per_period
    assert first.overall.metrics is None
    assert first.overall.mean_credits is None

    for period in result.periods[1:]:
        snapshot = period.aggregate.overall
        entering = sum(1 for s in result.students if entry[s.id] == period.period)
        assert snapshot.metrics is not None
        assert snapshot.metrics.students == snapshot.active - entering
        entering_cut = next(
            c for c in period.aggregate.by_cohort if c.group == str(period.period)
        )
        assert entering_cut.active == entering
        assert entering_cut.metrics is None


def entry_records(result, students):
    """O registro do período de ingresso de cada aluno."""
    entry = {s.id: s.entry_period for s in students}
    return [
        (history.student_id, record)
        for history in result.histories
        for record in history.periods
        if record.period == entry[history.student_id]
    ]


def test_entrants_get_every_entry_discipline_without_bidding():
    config = make_config(periods=6)
    result = run_simulation(config)
    first = set(config.entry_disciplines())
    assert first == {"D1", "D2"}

    records = entry_records(result, result.students)
    assert records, "toda geração deveria ter um período de ingresso registrado"
    for student_id, record in records:
        granted = {r.discipline for r in record.requests if r.won_round == GUARANTEED_ROUND}
        assert granted == first, f"{student_id} não recebeu a matrícula garantida inteira"
        assert {r.discipline for r in record.requests} == first
        served = sum(
            r.utility
            for r in record.requests
            if r.won_round is not None and not r.excluded
        )
        assert record.satisfaction == pytest.approx(served)
        assert 0 < record.satisfaction <= 1 + 1e-9


def test_the_system_charges_the_entrant_an_equal_share_of_the_budget():
    """"Gastaram seus créditos igualmente", com o resto da divisão no saldo."""
    config = make_config(periods=4, min_credits=10)
    result = run_simulation(config)
    first = config.entry_disciplines()
    share = config.min_credits // len(first)

    for _, record in entry_records(result, result.students):
        assert record.credits_start == config.min_credits
        assert all(r.paid == share for r in record.requests)
        assert record.credits_spent == share * len(first)
        remainder = config.min_credits - share * len(first)
        assert record.credits_end == max(
            remainder + record.credits_returned, config.min_credits
        )


def test_an_indivisible_budget_leaves_the_remainder_with_the_entrant():
    """Divisão inteira: com 7 créditos e 2 disciplinas, 3 em cada e 1 de sobra."""
    config = make_config(periods=2, min_credits=7)
    result = run_simulation(config)
    for _, record in entry_records(result, result.students):
        assert record.credits_spent == 6
        assert record.credits_end == max(1 + record.credits_returned, 7)


def test_the_entrant_share_feeds_the_credit_return():
    """O que a matrícula garantida entrega ao f_gamma da eq. (34): o valor"""
    config = make_config(periods=4, min_credits=10)
    result = run_simulation(config)
    share = config.min_credits // len(config.entry_disciplines())
    returned = [
        r
        for _, record in entry_records(result, result.students)
        for r in record.requests
        if r.approved
    ]
    assert returned, "alguém deveria aprovar na matrícula garantida"
    assert all(
        r.returned == credit_return(paid=share, grade=r.grade)
        for r in returned
    )


def test_the_guaranteed_seat_comes_out_of_the_offer_and_counts_as_a_request():
    """A vaga garantida sai da própria oferta da turma e entra com solicitação"""
    config = make_config()
    lotacao = config.seats_by_class()
    entrada = set(config.entry_disciplines())
    por_turma = config.students_per_entry_class

    result = run_simulation(config)
    for period in result.periods:
        for snapshot in period.disciplines:
            assert snapshot.seats == lotacao[snapshot.name]
            if snapshot.discipline not in entrada:
                assert snapshot.granted == 0
                continue
            assert snapshot.granted == por_turma
            assert por_turma <= snapshot.filled <= snapshot.seats
            assert snapshot.requests >= por_turma


def test_a_root_that_is_not_entry_is_not_granted():
    """A raiz sem o flag disputa vaga. Só a de entrada sai do estoque antes da rodada."""
    config = make_config(
        periods=1,
        rounds=1,
        disciplines=disciplines_from_predecessors(
            ("Entrada", 6, 60),
            ("Livre", 6, 60, False),
        ),
        max_hours=120,
        **single_axis(120),
    )
    result = run_simulation(config)
    granted = {d.name: d.granted for d in result.periods[0].disciplines}
    assert granted == {"Entrada": config.students_per_period, "Livre": 0}


def test_guaranteed_seats_leave_the_market_before_the_first_round():
    """A vaga entregue ao ingressante não é ofertada: ela já saiu do estoque"""
    config = make_config(periods=5)
    result = run_simulation(config)
    first = set(config.entry_disciplines())
    per_period = config.students_per_period

    for period in result.periods:
        for snapshot in period.disciplines:
            if snapshot.name in first and period.period <= config.entry_span:
                assert snapshot.granted == per_period
            else:
                assert snapshot.granted == 0


def test_a_generation_larger_than_the_smallest_entry_offer_is_rejected():
    """A garantia só é garantia se couber: o bloco da coorte que vai parar em"""
    with pytest.raises(ValueError, match="ingressantes por turma de entrada"):
        SimulationConfig(
            disciplines=[
                Discipline("D1", seats=5, hours=60, entry=True),
                Discipline("D2", seats=3, hours=60, entry=True),
            ],
            students_per_entry_class=4,
            max_hours=360, **single_axis(360),
        )
    assert SimulationConfig(
        disciplines=[
            Discipline("D1", seats=4, hours=60, entry=True),
            Discipline("D2", seats=4, hours=60, entry=True),
        ],
        students_per_entry_class=4,
        max_hours=360, **single_axis(360),
    ).students_per_period == 4


def test_entry_disciplines_heavier_than_the_workload_cap_are_rejected():
    """O ingressante cursa as de 1º período todas de uma vez: a carga somada"""
    with pytest.raises(ValueError, match="não cabem na carga horária máxima"):
        SimulationConfig(
            disciplines=[
                Discipline("D1", seats=5, hours=60, entry=True),
                Discipline("D2", seats=5, hours=60, entry=True),
            ],
            students_per_entry_class=2,
            max_hours=100,
            **single_axis(100),
        )


def test_retaking_an_entry_discipline_goes_through_the_auction():
    """A garantia vale só no ingresso: quem reprova em D1 disputa a vaga como"""
    config = make_config(periods=8)
    result = run_simulation(config)
    first = set(config.entry_disciplines())
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


def test_cohorts_partition_the_university():
    """`by_cohort` é o mesmo recorte de `overall`, fatiado por geração: somar as"""
    result = run_simulation(make_config())
    reports = [r for p in result.periods for r in (*p.rounds, p.aggregate)]
    assert reports

    for report in reports:
        assert report.overall.group is None, "o agregado não tem geração"
        assert sum(c.active for c in report.by_cohort) == report.overall.active
        assert sum(c.graduated for c in report.by_cohort) == report.overall.graduated
        assert sum(c.population for c in report.by_cohort) == report.overall.population
        entries = [c.group for c in report.by_cohort]
        assert len(set(entries)) == len(entries)
        assert all(entry is not None for entry in entries)


def test_a_student_never_changes_cohort():
    """É o que distingue a geração da idade: o aluno nasce numa geração e fica"""
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
    """Uma geração que já esvaziou continua na lista enquanto a simulação"""
    result = run_simulation(
        make_config(
            periods=12
        )
    )
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


def test_the_return_follows_the_grade_and_the_multiplier():
    """f_gamma — eq. (34): γ = round(nota/10 · k · preço), com k = 2 por padrão."""
    esperado = (10, 10, 18)
    got = tuple(credit_return(paid=10, grade=grade) for grade in (4.9, 5.0, 9.0))
    assert got == esperado

    for grade in (0.0, 3.3, 7.7, 10.0):
        assert credit_return(paid=0, grade=grade) == 0

    with pytest.raises(ValueError, match="negativo"):
        credit_return(paid=-1, grade=10.0)


def test_the_cut_grade_is_the_neutral_point_of_the_return():
    """A calibragem que justifica o multiplicador 2: aprovar com a nota de"""
    for paid in (1, 2, 5, 10, 17):
        assert credit_return(paid=paid, grade=5.0) == paid
        assert credit_return(paid=paid, grade=0.0) == 0

    assert credit_return(paid=1, grade=2.5) == 1
    assert credit_return(paid=1, grade=2.4) == 0
    assert credit_return(paid=10, grade=4.8) == 10
    assert credit_return(paid=10, grade=4.7) == 9


def test_the_rounding_has_no_bias_and_the_top_prize_follows_the_price():
    """O retorno **arredonda** (meio para cima) desde 17/11/2026; truncava"""
    for paid in (1, 2, 5, 10, 17):
        for decimos in range(101):
            grade = decimos / 10
            exato = grade / 10 * 2 * paid
            assert abs(credit_return(paid=paid, grade=grade) - exato) <= 0.5 + 1e-9
        assert credit_return(paid=paid, grade=10.0) == 2 * paid

    assert credit_return(paid=1, grade=7.5) == 2
    assert credit_return(paid=1, grade=7.4) == 1
    assert credit_return(paid=5, grade=9.5) == 10
    assert credit_return(paid=5, grade=9.4) == 9
    assert credit_return(paid=10, grade=9.8) == 20
    assert credit_return(paid=10, grade=9.7) == 19

    assert credit_return(paid=1, grade=2.5) == 1
    assert credit_return(paid=25, grade=1.4) == 7


def test_the_fixed_multiplier_makes_the_extremes_symmetric():
    """Por que o multiplicador vale 2 e deixou de ser parâmetro em 24/11/2026:"""
    for paid in (1, 2, 5, 10, 17):
        assert credit_return(paid=paid, grade=0.0) == 0
        assert credit_return(paid=paid, grade=10.0) == 2 * paid
        assert credit_return(paid=paid, grade=5.0) == paid


def test_credit_return_is_added_to_the_budget_of_the_next_period():
    """eq. (36): C_a^(t+1,1) = clamp(C_a^(t,1) - gasto + soma gamma, C_min, C_max)."""
    config = make_config(max_credits=None)
    result = run_simulation(config)
    for history in result.histories:
        for record in history.periods:
            assert record.credits_end == max(
                record.credits_start
                - record.credits_spent
                + record.credits_returned,
                config.min_credits,
            )
            assert record.credits_returned == sum(q.returned for q in record.requests)
            assert all(q.returned == 0 for q in record.requests if q.attempt is None)


def test_the_budget_never_leaves_the_credit_band():
    """A faixa vale em todo período e todo aluno, não só na transição."""
    config = make_config(min_credits=4, max_credits=6)
    result = run_simulation(config)
    for history in result.histories:
        for record in history.periods:
            assert config.min_credits <= record.credits_start <= config.max_credits
            assert config.min_credits <= record.credits_end <= config.max_credits


def test_the_return_lets_the_balance_grow_until_the_ceiling_cuts():
    """Sem crédito base somado, o retorno é a única entrada de crédito novo, e"""
    generoso = run_simulation(make_config(min_credits=4, max_credits=5))
    cortou = False
    subiu = False
    for history in generoso.histories:
        for record in history.periods:
            bruto = (
                record.credits_start - record.credits_spent + record.credits_returned
            )
            assert record.credits_end == min(max(bruto, 4), 5)
            cortou |= bruto > 5
            subiu |= bruto > 4
    assert subiu, "o saldo não chegou a subir — o cenário não exercita a regra"
    assert cortou, "o teto não chegou a cortar — o cenário não exercita a regra"


def test_a_maximum_below_the_minimum_is_refused():
    """C_max < C_min seria uma faixa vazia: o piso estoura o próprio teto."""
    with pytest.raises(ValueError, match="C_max"):
        make_config(min_credits=10, max_credits=9)


def test_the_band_clamps_the_accumulated_balance_on_both_sides():
    """A conta pura da eq. (36) — fronteira a fronteira, nos dois extremos."""
    conta = dict(started_with=20, spent=5, period_return=12)

    assert next_budget(**conta, min_credits=12) == 27
    assert next_budget(**conta, min_credits=12, max_credits=None) == 27
    assert next_budget(**conta, min_credits=12, max_credits=30) == 27
    assert next_budget(**conta, min_credits=12, max_credits=27) == 27
    assert next_budget(**conta, min_credits=12, max_credits=20) == 20

    gastou_tudo = dict(started_with=20, spent=20, period_return=3)
    assert next_budget(**gastou_tudo, min_credits=12) == 12
    assert next_budget(**gastou_tudo, min_credits=3, max_credits=30) == 3
    assert next_budget(**gastou_tudo, min_credits=1) == 3


def test_the_return_matches_the_equation_inside_a_full_simulation():
    """O gamma registrado por disciplina tem de bater com a eq. (34) rodando a"""
    result = run_simulation(make_config())
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
            paid=request.paid, grade=request.grade
        )

    alunos = run_simulation(make_config()).students
    assert any(s.credits > 12 for s in alunos)


def test_credit_return_is_reported_only_at_the_end_of_the_period():
    """Durante as rodadas as notas ainda não saíram: o recorte traz `None`, não"""
    config = make_config()
    result = run_simulation(config)
    for period in result.periods:
        for report in period.rounds:
            assert report.overall.mean_credit_return is None
            assert all(c.mean_credit_return is None for c in report.by_cohort)
        for snapshot in period.aggregate.by_cohort:
            assert (snapshot.mean_credit_return is None) == (snapshot.metrics is None)

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
            if received and snapshot.metrics is not None:
                assert snapshot.mean_credit_return == pytest.approx(
                    sum(received) / len(received)
                )


def test_scenario_without_students_or_disciplines_is_rejected():
    """Garantia de que todo período tem aluno começa na entrada: um cenário sem"""
    with pytest.raises(ValueError, match="pelo menos um ingressante"):
        SimulationConfig(
            disciplines=[Discipline("D1", seats=5, hours=60)],
            students_per_entry_class=0,
            max_hours=360, **single_axis(360),
        )
    with pytest.raises(ValueError, match="pelo menos uma disciplina"):
        SimulationConfig(students_per_entry_class=5, max_hours=360, **single_axis(360))


def test_every_period_receives_a_generation():
    """O ingresso é contínuo: toda coorte entra, do primeiro período ao último."""
    config = make_config(periods=7)
    assert config.entry_span == 7
    assert {s.entry_period for s in run_simulation(config).students} == set(range(1, 8))


def test_the_population_is_constant_once_the_residence_is_full():
    """O porquê de a pré-população ser o prazo de jubilamento."""
    residence = 4
    config = make_config(periods=8, max_residence=residence, approval_rate=1e-9)
    result = run_simulation(config)
    ativos = {p.period: p.aggregate.overall.active for p in result.periods}
    coorte = config.students_per_period

    for period in range(1, residence + 1):
        assert ativos[period] == coorte * period, period
    for period in range(residence, 9):
        assert ativos[period] == coorte * residence, period


def test_the_measurement_starts_when_the_cohort_enters():
    """A pré-população roda inteira — o motor não joga nada fora — e a medição
    começa no **ingresso** da coorte medida, que é o último período dela."""
    config = make_config(periods=8, warmup_periods=3)
    result = run_simulation(config)
    assert len(result.periods) == 8
    assert config.measured_cohort == 3
    assert [p.period for p in result.observed] == [3, 4, 5, 6, 7, 8]


def test_only_the_measured_cohort_enters_the_averages():
    """Duas fases, uma coorte: quem entra fora de t = j roda, disputa e conta"""
    config = make_config(periods=8, warmup_periods=3)
    assert config.measured_cohort == 3
    result = run_simulation(config)

    def ativos(period: int, da_coorte: bool) -> int:
        return sum(
            1
            for s in result.students
            if s.entry_period <= period
            if (s.graduated_at or s.dismissed_at or period) >= period
            if (s.entry_period == 3) == da_coorte
        )

    for period in result.observed:
        snapshot = period.aggregate.overall
        assert snapshot.metrics is not None, period.period
        assert snapshot.metrics.students == ativos(period.period, True), period.period
        assert ativos(period.period, False) > 0, period.period
        assert snapshot.active > snapshot.metrics.students, period.period


def test_without_a_warmup_everybody_but_the_freshman_is_measured():
    """Sem pré-população não há coorte a eleger, e o recorte volta a ser o"""
    config = make_config(periods=4)
    assert config.measured_cohort is None
    result = run_simulation(config)
    for period in result.observed:
        snapshot = period.aggregate.overall
        if snapshot.metrics is None:
            continue
        calouros = sum(
            1 for s in result.students if s.entry_period == period.period
        )
        assert snapshot.metrics.students == snapshot.active - calouros


def test_a_warmup_that_eats_the_horizon_is_refused():
    with pytest.raises(ValueError, match="pré-população"):
        make_config(periods=3, warmup_periods=3)


def test_population_counts_everyone_who_entered_the_cut():
    """`population` é o denominador da fração de formados: quem já ingressou no"""
    config = make_config(periods=8)
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
    """A soma ingênua conta duas vezes quem se forma ao fim do período: ele"""
    result = run_simulation(make_config(periods=8))
    naive = [
        (snapshot.active + snapshot.graduated, snapshot.population)
        for period in result.periods
        for snapshot in period.aggregate.by_cohort
    ]
    assert all(total >= population for total, population in naive)
    assert any(total > population for total, population in naive)


def test_minimum_periods_to_graduate_takes_the_tighter_of_the_two_limits():
    """São dois pisos — a carga horária e a cadeia de pré-requisitos — e vale o"""
    config = make_config()
    assert config.hours_to_graduate() == 360
    assert config.minimum_periods_to_graduate() == 3

    wide = SimulationConfig(
        disciplines=disciplines_from_predecessors(
            ("A", 5, 60),
            ("B", 5, 60, ("A",)),
            ("C", 5, 60, ("A",)),
            ("D", 5, 60, ("A",)),
            ("E", 5, 60, ("A",)),
        ),
        students_per_entry_class=5,
        max_hours=60,
        **single_axis(60),
    )
    assert wide.hours_to_graduate() == 300
    assert max(wide.curriculum_periods().values()) == 2
    assert wide.minimum_periods_to_graduate() == 5

    doomed = run_simulation(make_config(periods=2))
    assert all(s.graduated_at is None for s in doomed.students)


ELECTIVES = [
    Discipline(f"OPT{i}", seats=36, hours=60, elective=True) for i in range(1, 7)
]
ELECTIVE_QUOTA = 120


def make_elective_config(**overrides) -> SimulationConfig:
    return make_config(
        disciplines=GRADE + ELECTIVES,
        elective_hours=ELECTIVE_QUOTA,
        periods=12,
        **overrides,
    )


def test_electives_stay_out_of_the_guaranteed_enrollment():
    """A optativa é de 1º período na indução (não tem pré-requisito), mas dar"""
    config = make_elective_config()
    first = config.entry_disciplines()
    assert first == ["D1", "D2"]
    assert all(config.curriculum_periods()[d.name] == 1 for d in ELECTIVES)

    result = run_simulation(config)
    guaranteed = {
        record.discipline
        for history in result.histories
        for period in history.periods
        for record in period.requests
        if record.won_round == GUARANTEED_ROUND
    }
    assert guaranteed == {"D1", "D2"}


def test_graduating_requires_the_elective_hours_not_every_elective():
    """A eq. (40) estendida: todas as obrigatórias, mais X horas somadas entre"""
    config = make_elective_config()
    result = run_simulation(config)
    names = {d.name for d in ELECTIVES}
    done = [s for s in result.students if s.graduated_at is not None]
    assert done, "ninguém concluiu o curso"

    by_id = {h.student_id: h for h in result.histories}
    for student in done:
        approved = {
            record.discipline
            for period in by_id[student.id].periods
            for record in period.requests
            if record.approved
        }
        assert {d.name for d in GRADE} <= approved
        taken = approved & names
        assert sum(60 for _ in taken) >= ELECTIVE_QUOTA
        assert len(taken) < len(names)


def test_electives_leave_the_eligible_set_once_the_requirement_is_met():
    config = make_elective_config()
    assert "OPT1" in config.eligible_disciplines(set())
    assert "OPT3" in config.eligible_disciplines({"OPT1"})
    met = config.eligible_disciplines({"OPT1", "OPT2"})
    assert not any(name.startswith("OPT") for name in met)
    assert "D1" in met


def test_progress_tops_out_at_one_even_with_elective_hours_to_spare():
    """Quem passa da exigência optativa não passa de 1 no progresso: a parcela"""
    config = make_elective_config()
    result = run_simulation(config)
    sobrando = [
        s for s in result.students if s.approved_hours > config.hours_to_graduate()
    ]
    assert sobrando, "ninguém passou da exigência — o corte não é exercitado"

    medidos = 0
    for report in result.periods:
        metrics = report.aggregate.overall.metrics
        if metrics is None:
            continue
        medidos += 1
        assert 0.0 <= metrics.progress <= 1.0
    assert medidos, "nenhum período publicou métrica"


def test_hours_to_graduate_counts_required_plus_the_quota():
    """Não é a carga da grade inteira: o catálogo de optativas é maior que a"""
    config = make_elective_config()
    assert config.hours_to_graduate() == 6 * 60 + ELECTIVE_QUOTA
    assert sum(d.hours for d in config.disciplines) == 12 * 60


def test_an_elective_cannot_have_prerequisites():
    """A optativa existe para estar sempre ao alcance; quem desbloqueia uma"""
    with pytest.raises(ValueError, match="optativa .* não pode ter pré-requisito"):
        make_config(
            disciplines=[
                Discipline("D1", seats=6, hours=60, unlocks=("OPT",), entry=True),
                Discipline("OPT", seats=6, hours=60, elective=True),
            ],
            elective_hours=60,
        )


def test_an_elective_cannot_unlock_anything():
    """Se destravasse, a cadeia passaria a depender de uma disciplina que"""
    with pytest.raises(ValueError, match="não pode desbloquear nada"):
        Discipline("OPT", seats=1, hours=60, unlocks=("D3",), elective=True)


def test_an_elective_cannot_be_an_entry_discipline():
    with pytest.raises(ValueError, match="não pode ser de entrada"):
        Discipline("OPT", seats=1, hours=60, elective=True, entry=True)


def test_the_elective_requirement_must_fit_the_offer():
    with pytest.raises(ValueError, match="não cabe nas .* h ofertadas"):
        make_config(disciplines=GRADE + ELECTIVES, elective_hours=10 * 60)


def test_entry_validations_ignore_electives():
    """Os dois limites do ingresso — geração contra a menor oferta e carga"""
    config = make_elective_config()
    entry = config.entry_disciplines()
    assert entry == ["D1", "D2"]
    assert sum(d.hours for d in GRADE if d.name in entry) <= config.max_hours

    assert sum(d.hours for d in ELECTIVES) > config.max_hours

    tight = make_config(
        disciplines=GRADE + [Discipline("OPT_RARA", seats=1, hours=60, elective=True)],
        elective_hours=60,
        periods=12,
    )
    assert tight.entry_disciplines() == ["D1", "D2"]


def test_progress_is_the_approved_hours_over_the_hours_to_graduate():
    """Progresso = carga aprovada ÷ carga que conclui o curso (S)."""
    config = make_config(periods=6)
    result = run_simulation(config)
    total = config.hours_to_graduate()
    assert total == sum(d.hours for d in GRADE)

    entry = {s.id: s.entry_period for s in result.students}
    by_period: dict[int, list[float]] = {}
    for history in result.histories:
        for record in history.periods:
            if record.period == entry[history.student_id]:
                continue
            by_period.setdefault(record.period, []).append(
                record.approved_hours / total
            )

    medidos = 0
    for report in result.periods:
        metrics = report.aggregate.overall.metrics
        if metrics is None:
            continue
        medidos += 1
        shares = by_period[report.period]
        assert metrics.progress == pytest.approx(sum(shares) / len(shares))
        assert 0.0 <= metrics.progress <= 1.0
    assert medidos, "nenhum período publicou métrica — o cenário não exercita a regra"


def test_progress_without_a_curriculum_to_close_is_zero_not_a_division():
    """W_obg + X = 0 não é cenário do simulador — a validação exige grade —,"""
    def progresso(obrigatoria=0, optativa=0, exige_obrigatoria=0, exige_optativa=0):
        return progress(
            approved_required_hours=obrigatoria,
            approved_elective_hours=optativa,
            required_hours=exige_obrigatoria,
            elective_hours_needed=exige_optativa,
        )

    assert progresso() == 0.0
    assert progresso(obrigatoria=30) == 0.0
    assert progresso(obrigatoria=30, exige_obrigatoria=120) == 0.25


def test_the_elective_counts_only_up_to_the_quota():
    """O teto é 1, e chegar a 1 é a eq. (40): a obrigatória entra inteira, a"""
    def progresso(obrigatoria, optativa):
        return progress(
            approved_required_hours=obrigatoria,
            approved_elective_hours=optativa,
            required_hours=360,
            elective_hours_needed=120,
        )

    assert progresso(360, 120) == 1.0
    assert progresso(360, 480) == 1.0
    assert progresso(300, 480) == pytest.approx(420 / 480)
    assert progresso(180, 60) == 0.5


def test_dismissal_lands_on_the_last_period_of_residence():
    """Quem entra em t_a cursa os períodos de residência a partir dali, e é ao"""
    config = make_config(periods=9, max_residence=4, approval_rate=1e-9)
    result = run_simulation(config)
    assert all(s.graduated_at is None for s in result.students)
    for student in result.students:
        fim = student.entry_period + 4 - 1
        if fim <= config.periods:
            assert student.dismissed_at == fim
        else:
            assert student.dismissed_at is None


def test_the_two_exits_are_exclusive_and_graduation_wins():
    """Conclusão e jubilamento são exclusivos, e a ordem importa: quem fecha a"""
    loose = run_simulation(make_config(periods=12))
    graduated = [s for s in loose.students if s.graduated_at is not None]
    assert graduated, "ninguém concluiu nem sem prazo"
    first = min(graduated, key=lambda s: s.graduated_at - s.entry_period)
    residence = first.graduated_at - first.entry_period + 1

    tight = run_simulation(
        make_config(periods=12, max_residence=residence)
    )
    for student in tight.students:
        assert not (student.graduated_at and student.dismissed_at)
    on_the_wire = next(s for s in tight.students if s.id == first.id)
    assert on_the_wire.graduated_at == first.graduated_at
    assert on_the_wire.dismissed_at is None


def test_the_dismissed_stop_disputing():
    """Jubilado sai de `active` e não aparece em período nenhum depois disso —"""
    result = run_simulation(make_config(periods=9, max_residence=4,
                                        approval_rate=1e-9))
    by_id = {s.id: s for s in result.students}
    for history in result.histories:
        student = by_id[history.student_id]
        if history.periods and student.dismissed_at is not None:
            assert max(r.period for r in history.periods) <= student.dismissed_at


def test_without_max_residence_nobody_is_dismissed():
    """`None` desliga o jubilamento e devolve o modelo em que a conclusão é a"""
    result = run_simulation(make_config(periods=12, approval_rate=1e-9))
    assert all(s.dismissed_at is None for s in result.students)
    last = result.periods[-1].aggregate.overall
    assert last.dismissed == 0


def test_the_horizon_is_the_warmup_plus_the_observation():
    """|T| derivado: a pré-população é o prazo de jubilamento, e depois dela"""
    assert horizon_for_window(max_residence=5) == 9
    config = make_config(periods=8, max_residence=5, warmup_periods=5)
    result = run_simulation(config)
    assert [p.period for p in result.observed] == [5, 6, 7, 8]