"""O fim do período: exclusão, notas, retorno de créditos, conclusão e
jubilamento.

Depois da última rodada o aluno **exclui** o que não couber na disponibilidade
dele; só então saem as notas (eq. 33) do que ficou, o retorno de créditos
(eq. 34), o saldo do período seguinte (eq. 36), as conclusões (eq. 40) e os
jubilamentos. É a única parte da simulação que escreve no `Student`.

A **exclusão vem primeiro** e é o que define o escopo de todo o resto: a
disciplina excluída não recebe nota, não entra no CR, não soma carga cursada e
não gasta tentativa — quem exclui e refaz no semestre seguinte volta como
primeira tentativa, sem o ganho de recursada. No leilão ela devolve metade do
preço pago (`equations.exclusion_refund`); a vaga, essa não volta para a
oferta, porque a esta altura as alocações do período já se encerraram.

As duas saídas são exclusivas e **nesta ordem**: quem fecha a grade no último
período de residência conta como concluinte, não como jubilado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import SimulationConfig
from ..equations import (
    credit_return,
    effective_load,
    exclusion_refund,
    grade_for_attempt,
    has_graduated,
    next_budget,
    period_return,
    retained_set,
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
    # O que o aluno levou e o que largou, do que tinha obtido. A soma dos dois
    # é `state.won`: a vaga saiu do sistema de qualquer jeito, e é a diferença
    # entre os dois conjuntos que mede desperdício.
    retained: dict[str, set[str]] = field(default_factory=dict)
    excluded: dict[str, list[str]] = field(default_factory=dict)
    exclusions: dict[str, int] = field(default_factory=dict)  # por disciplina
    load: dict[str, int] = field(default_factory=dict)  # Ŵ_a^(t), por aluno
    first_grades: list[float] = field(default_factory=list)
    graduated_now: int = 0
    dismissed_now: int = 0


def _grade(
    *,
    student: Student,
    name: str,
    attempt: int,
    draws: Draws,
) -> float:
    """A nota desta tentativa — ver `equations.grade_for_attempt`.

    A dificuldade e a tentativa escolhem a distribuição; o quantil do aluno
    diz onde ele cai dentro dela. A utilidade não entra: ela já governa o que
    ele pede e o que ele exclui.
    """
    mode, left_sd, right_sd = draws.grade_shapes.of(
        student.performance, draws.difficulty[name], attempt
    )
    return grade_for_attempt(
        quantile=draws.base_quantiles[(student.id, name)],
        mode=mode,
        left_sd=left_sd,
        right_sd=right_sd,
    )


def close_period(
    *,
    config: SimulationConfig,
    draws: Draws,
    active: list[Student],
    state: PeriodState,
    period: int,
    utilities: dict[str, dict[str, float]],
    enrollments: dict[str, int],
) -> PeriodClosing:
    closing = PeriodClosing(
        approvals={d.name: 0 for d in config.disciplines},
        exclusions={d.name: 0 for d in config.disciplines},
    )

    for student in active:
        allocated = state.won[student.id]
        # A mochila do que ele leva: valor = utilidade, peso = carga, teto = as
        # horas que a disponibilidade deste período lhe deu. O que sobra é
        # excluído — ver `equations.retained_set`. O teto pode passar de W_a, e
        # aí ele não exclui nada: o limite de carga é do alocador, não do aluno.
        load = effective_load(
            availability=draws.availability[(student.id, period)]
        )
        kept = retained_set(
            utilities=utilities[student.id],
            hours=draws.hours,
            obtained=allocated,
            load=load,
        )
        closing.load[student.id] = load
        retained = set(kept)
        excluded = sorted(allocated - retained)
        closing.retained[student.id] = retained
        closing.excluded[student.id] = excluded

        # `enrollments` conta o que ele de fato cursou: a excluída ocupou vaga,
        # mas não virou matrícula. Quem mede a vaga consumida é `state.won`.
        enrollments[student.id] += len(retained)
        gammas: list[int] = []

        for name in excluded:
            closing.exclusions[name] += 1
            gamma = (
                exclusion_refund(
                    config.credit_return,
                    paid=state.paid.get((student.id, name), 0),
                )
                if config.uses_credits
                else 0
            )
            closing.returned[(student.id, name)] = gamma
            gammas.append(gamma)

        # A ordem é a da grade, vinda da mochila — e não a de um conjunto, que
        # varia com o hash das strings entre observações.
        for name in kept:
            attempt = student.attempts.get(name, 0) + 1
            student.attempts[name] = attempt
            grade = _grade(
                student=student, name=name, attempt=attempt, draws=draws
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
