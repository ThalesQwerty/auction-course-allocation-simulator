"""O fim do período: notas, retorno de créditos, conclusão e jubilamento.

Depois da última rodada saem as notas (eq. 33) das disciplinas obtidas, o
retorno de créditos que elas geram (eq. 34), o saldo do período seguinte
(eq. 36), as conclusões (eq. 40) e os jubilamentos. É a única parte da
simulação que escreve no `Student`.

As duas saídas são exclusivas e **nesta ordem**: quem fecha a grade no último
período de residência conta como concluinte, não como jubilado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import SimulationConfig
from ..equations import (
    credit_return,
    grade_for_attempt,
    has_graduated,
    next_budget,
    period_return,
)
from ..population import Student
from .setup import Draws
from .state import PeriodState


@dataclass
class PeriodClosing:
    """O que o fim do período produziu, para os relatórios."""

    approvals: dict[str, int]  # por disciplina
    # (aluno, disciplina) -> (tentativa, nota **desta** tentativa)
    attempts: dict[tuple[str, str], tuple[int, float]] = field(default_factory=dict)
    returned: dict[tuple[str, str], int] = field(default_factory=dict)  # γ_{a,x}
    credits_returned: dict[str, int] = field(default_factory=dict)  # Σγ por aluno
    first_grades: list[float] = field(default_factory=list)
    graduated_now: int = 0
    dismissed_now: int = 0


def _grade(
    *,
    student: Student,
    name: str,
    attempt: int,
    period: int,
    config: SimulationConfig,
    draws: Draws,
) -> float:
    """A nota desta tentativa — ver `equations.grade_for_attempt`."""
    return grade_for_attempt(
        aptitude=draws.aptitudes[(student.id, name)],
        difficulty=draws.difficulty[name],
        # u_rel: a utilidade em múltiplos da indiferença. Sai da linha
        # sorteada, não do recorte elegível — é a mesma grandeza em qualquer
        # período, e é isso que a torna comparável.
        relative_utility=draws.utility_rows[(student.id, period)][name]
        * draws.catalogue,
        attempt=attempt,
        utility_gain=config.utility_gain,
        retake_gain=config.retake_gain,
    )


def close_period(
    *,
    config: SimulationConfig,
    draws: Draws,
    active: list[Student],
    state: PeriodState,
    period: int,
    enrollments: dict[str, int],
) -> PeriodClosing:
    closing = PeriodClosing(
        approvals={d.name: 0 for d in config.disciplines}
    )

    for student in active:
        enrollments[student.id] += len(state.won[student.id])
        gammas: list[int] = []

        for name in state.won[student.id]:
            attempt = student.attempts.get(name, 0) + 1
            student.attempts[name] = attempt
            grade = _grade(
                student=student,
                name=name,
                attempt=attempt,
                period=period,
                config=config,
                draws=draws,
            )
            if attempt == 1:
                closing.first_grades.append(grade)
            # `grades` guarda a **maior** nota já obtida — é ela que conta
            # para o CR e para a aprovação. O histórico, ao contrário, guarda
            # a desta tentativa: com a aptidão fixa mas o expoente caindo a
            # cada recursada, a nota nova raramente é menor, mas a tela
            # individual precisa mostrar o que aconteceu no período.
            student.grades[name] = max(student.grades.get(name, 0.0), grade)
            closing.attempts[(student.id, name)] = (attempt, grade)
            if student.grades[name] >= config.min_grade:
                closing.approvals[name] += 1

            # f_γ é do leilão: devolve parte do *preço pago*. Na linha de base
            # não houve preço nem pagamento, então não há o que devolver,
            # qualquer que seja a política escolhida.
            gamma = (
                credit_return(
                    config.credit_return,
                    paid=state.paid.get((student.id, name), 0),
                    grade=student.grades[name],
                    min_grade=config.min_grade,
                )
                if config.uses_credits
                else 0
            )
            closing.returned[(student.id, name)] = gamma
            gammas.append(gamma)

        closing.credits_returned[student.id] = sum(gammas)

        # Fora do leilão o saldo não se move: nada foi gasto, e inflá-lo com
        # Γ_min a cada período daria um número sem significado.
        if config.uses_credits:
            student.credits = next_budget(
                config.credit_memory,
                started_with=student.credits,
                spent=state.spent[student.id],
                period_return=period_return(
                    base_credits=config.base_credits, returns=gammas
                ),
                base_credits=config.base_credits,
            )

        if has_graduated(
            approved=student.approved(config.min_grade),
            required=draws.required,
            elective_hours_by_discipline=draws.elective_hours_by_discipline,
            elective_hours_needed=config.elective_hours,
        ):
            student.graduated_at = period
            closing.graduated_now += 1
        elif config.dismissal_period(student.entry_period) == period:
            # Jubilamento: esgotou os períodos de residência sem fechar a
            # grade. Vem **depois** da conclusão de propósito — quem fecha a
            # grade no último período permitido sai pela porta da frente.
            student.dismissed_at = period
            closing.dismissed_now += 1

    return closing
