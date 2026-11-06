"""Simulação multi-período da matrícula universitária (Seção 7.2).

Amarra as peças: a inicialização sorteia tudo da seed (`setup`), cada período
roda as suas rodadas e fecha com notas e conclusões (`period`, `rounds`,
`closing`), e os relatórios saem recortados por coorte (`snapshots`,
`reports`). As contas moram em `equations/`.

Não há cursos: a universidade inteira cursa a mesma grade. Toda disciplina
obrigatória tem de ser aprovada; as optativas valem pela carga somada.

**Quem ingressa não disputa as disciplinas de entrada** — recebe vaga
garantida nelas e fica fora do leilão naquele período para esse conjunto.
Entrada é uma flag do cenário, e não "não ter pré-requisito": a optativa
também não tem e fica fora da garantia.

O aluno sai do conjunto ativo por uma única porta: concluindo o curso
(eq. 40). Quem não concluiu continua disputando até o fim do horizonte, e é a
fase de drenagem que dá às coortes tardias tempo de chegar lá.

**Dois mecanismos, um cenário.** `config.mechanism` troca só o miolo da
rodada. Tudo o mais — população, utilidades, notas, pré-requisitos, matrícula
garantida, conclusão e métricas — é idêntico, que é a condição metodológica
da Seção 7.3: os dois lados partem da mesma inicialização, e por isso a
diferença entre eles é atribuível ao mecanismo.
"""
from __future__ import annotations

from ..config import SimulationConfig
from ..equations import grade_histogram, interest_histogram
from ..equations._mean import mean
from .period import run_period
from .reports import (
    GUARANTEED_ROUND,
    DisciplineSnapshot,
    GroupSnapshot,
    PeriodReport,
    PriceStats,
    RequestRecord,
    RoundReport,
    SimulationResult,
    StudentHistory,
    StudentPeriodRecord,
    StudentSummary,
)
from .setup import prepare

__all__ = [
    "GUARANTEED_ROUND",
    "DisciplineSnapshot",
    "GroupSnapshot",
    "PeriodReport",
    "PriceStats",
    "RequestRecord",
    "RoundReport",
    "SimulationResult",
    "StudentHistory",
    "StudentPeriodRecord",
    "StudentSummary",
    "run_simulation",
]


def run_simulation(config: SimulationConfig) -> SimulationResult:
    """Roda a simulação inteira. Determinística: mesma config, mesmo resultado.

    **Invariante dos relatórios**: todo período publicado tem pelo menos um
    aluno ativo, e a numeração vai de 1 a `len(periods)` sem buraco. Vale por
    construção — os ingressos ocorrem em períodos consecutivos a partir do
    primeiro e, passado o último deles, a população só diminui, então o primeiro
    período vazio só é seguido de períodos vazios. A simulação para ali.
    """
    draws = prepare(config)
    students = draws.students

    periods: list[PeriodReport] = []
    history: dict[str, list[StudentPeriodRecord]] = {s.id: [] for s in students}
    satisfactions: dict[str, list[float]] = {s.id: [] for s in students}
    enrollments: dict[str, int] = {s.id: 0 for s in students}
    first_grades: list[float] = []
    # No 1º período não há histórico, e os dois índices caem no neutro de 1/2
    # sozinhos — os genes de oferta e de aprovação não agem.

    for period in range(1, config.periods + 1):
        # Matriculados: já ingressaram (t_a) e ainda não saíram — por
        # conclusão (eq. 40) ou por jubilamento.
        active = [
            s for s in students if s.entry_period <= period and s.left_at is None
        ]
        if not active:
            break

        outcome = run_period(
            config=config,
            draws=draws,
            period=period,
            active=active,
            enrollments=enrollments,
        )
        if outcome is None:
            break

        periods.append(outcome.report)
        first_grades.extend(outcome.first_grades)
        for student_id, record in outcome.records.items():
            history[student_id].append(record)
            satisfactions[student_id].append(outcome.satisfaction[student_id])

    return SimulationResult(
        periods=periods,
        students=[
            StudentSummary(
                id=s.id,
                name=s.name,
                entry_period=s.entry_period,
                performance=s.performance.name,
                availability=s.availability.name,
                selectivity=s.selectivity.name,
                concentration=s.concentration.name,
                grade_average=s.grade_average(draws.discipline_hours),
                approved_hours=s.approved_hours(
                    draws.discipline_hours, config.min_grade
                ),
                hours_to_graduate=draws.hours_to_graduate,
                credits=s.credits,
                enrollments=enrollments[s.id],
                approvals=len(s.approved(config.min_grade)),
                mean_satisfaction=mean(satisfactions[s.id]),
                graduated_at=s.graduated_at,
                dismissed_at=s.dismissed_at,
            )
            for s in students
        ],
        histories=[
            StudentHistory(student_id=s.id, periods=history[s.id]) for s in students
        ],
        disciplines=list(draws.seats),
        classes=dict(draws.discipline_of),
        curriculum_periods=draws.curriculum,
        interest_distribution=interest_histogram(draws.interest_rows.values()),
        grade_distribution=grade_histogram(first_grades),
    )
