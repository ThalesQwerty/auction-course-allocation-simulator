"""Como um instante da simulação vira linhas de relatório.

Dois recortes do mesmo instante: a universidade inteira e cada geração. O
recorte **particiona** a população do agregado, então somá-lo reproduz
`overall` — é isso que permite trocar de agregação sem trocar de gráfico.

O eixo é genérico de propósito (`Axis`): um recorte novo é uma chave e uma
ordem. Foi assim que os recortes por perfil entraram e saíram.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from ..config import SimulationConfig
from ..equations import (
    credits_per_seat,
    message_fidelity,
    semestralization,
    utilization,
)
from ..equations._mean import mean
from ..metrics import compute_metrics
from ..population import Student
from .reports import GroupSnapshot


@dataclass(frozen=True)
class Axis:
    """Como rotular cada aluno e em que ordem as séries saem."""

    key: Callable[[Student], str]
    order: list[str]

    @classmethod
    def cohorts(cls, entry_periods: list[int], period: int) -> "Axis":
        """O eixo das gerações até o período corrente.

        Uma geração só entra na lista depois do seu t_a, e nunca mais sai —
        nem quando esvazia na fase de drenagem, senão a série dela sumiria
        justamente quando termina de contar por onde cada um saiu.
        """
        return cls(
            key=lambda s: str(s.entry_period),
            order=[str(entry) for entry in entry_periods if entry <= period],
        )


@dataclass(frozen=True)
class Measurements:
    """As grandezas por aluno de um instante, já calculadas.

    Todas indexadas por id. O que decide quem entra em cada média é
    `snapshot`, não este registro — aqui estão os valores de todo mundo.
    """

    satisfactions: dict[str, float]
    utilizations: dict[str, float]
    fidelities: dict[str, float]
    grade_averages: dict[str, float]
    semestralizations: dict[str, float]
    scarcities: dict[str, float]
    contentions: dict[str, float]
    approved_hours: dict[str, int]
    won: dict[str, set[str]]
    credits: dict[str, int]  # saldo no instante
    supply: dict[str, int]  # C_a^(t,1), a oferta do início do período
    bids: dict[str, int]
    credit_returns: dict[str, int] | None


def measure(
    *,
    config: SimulationConfig,
    active: list[Student],
    satisfactions: dict[str, float],
    grade_averages: dict[str, float],
    scarcities: dict[str, float],
    contentions: dict[str, float],
    won: dict[str, set[str]],
    messages: dict[str, dict[str, float]],
    utilities: dict[str, dict[str, float]],
    credits: dict[str, int],
    supply: dict[str, int],
    bids: dict[str, int],
    ages: dict[str, int],
    hours: dict[str, int],
    credit_returns: dict[str, int] | None,
) -> Measurements:
    """Calcula as grandezas que dependem do instante.

    `ages` vem do chamador porque acompanha o instante do recorte: nas
    rodadas de t o aluno completou t − t_a períodos; ao fim de t, um a mais —
    e é esse intervalo que a carga aprovada do mesmo recorte cobre.
    """
    approved_hours = {s.id: s.approved_hours(hours, config.min_grade) for s in active}
    return Measurements(
        satisfactions=satisfactions,
        # Aproveitamento sai de `won`, e não da carga aprovada, porque mede
        # alocação e não desempenho: a disciplina conta assim que a vaga é
        # obtida, reprove o aluno nela ou não.
        utilizations={
            s.id: utilization(won=won[s.id], hours=hours, max_hours=config.max_hours)
            for s in active
        },
        fidelities={
            s.id: message_fidelity(
                utilities=utilities[s.id], message=messages.get(s.id, {})
            )
            for s in active
        },
        grade_averages=grade_averages,
        semestralizations={
            s.id: semestralization(
                approved_hours=approved_hours[s.id],
                max_hours=config.max_hours,
                periods_completed=ages[s.id],
            )
            for s in active
        },
        scarcities=scarcities,
        contentions=contentions,
        approved_hours=approved_hours,
        won=won,
        credits=credits,
        supply=supply,
        bids=bids,
        credit_returns=credit_returns,
    )


def snapshot(
    *,
    group: str | None,
    members: list[Student],
    measured: list[Student],
    values: Measurements,
    total_seats: int,
    population: int,
    graduated: int,
    dismissed: int,
    uses_credits: bool,
) -> GroupSnapshot:
    """Um recorte qualquer: a universidade inteira ou uma geração.

    `members` é quem está matriculado — a contagem de pessoas. `measured` é o
    subconjunto que de fato disputou: os mesmos, menos os calouros do
    período. Toda média sai de `measured`, e só `active` sai de `members`.

    Sem crédito no cenário as cinco grandezas de crédito saem `None`, como já
    saem num recorte vazio: ali não houve ninguém, aqui não há moeda.
    """
    if not measured:
        return GroupSnapshot(
            group=group,
            metrics=None,
            active=len(members),
            population=population,
            graduated=graduated,
            dismissed=dismissed,
            mean_credits=None,
            mean_approved_hours=None,
            credits_per_student=None,
            credits_per_seat=None,
            mean_bids=None,
            mean_credit_return=None,
        )

    ids = [s.id for s in measured]
    supply = sum(values.supply[i] for i in ids)

    def pick(source: dict[str, float]) -> list[float]:
        return [source[i] for i in ids]

    def in_credits(value: float) -> float | None:
        """Grandeza de crédito: `None` onde não há moeda."""
        return value if uses_credits else None

    return GroupSnapshot(
        group=group,
        metrics=compute_metrics(
            satisfactions=pick(values.satisfactions),
            utilizations=pick(values.utilizations),
            fidelities=pick(values.fidelities),
            grade_averages=pick(values.grade_averages),
            semestralizations=pick(values.semestralizations),
            scarcities=pick(values.scarcities),
            contentions=pick(values.contentions),
            allocated=sum(len(values.won[i]) for i in ids),
            total_seats=total_seats,
        ),
        active=len(members),
        population=population,
        graduated=graduated,
        dismissed=dismissed,
        mean_credits=in_credits(mean(pick(values.credits))),
        mean_approved_hours=mean(pick(values.approved_hours)),
        credits_per_student=in_credits(supply / len(ids)),
        credits_per_seat=(
            credits_per_seat(supply=supply, total_seats=total_seats)
            if uses_credits
            else None
        ),
        mean_bids=in_credits(mean(pick(values.bids))),
        mean_credit_return=(
            mean([values.credit_returns[i] for i in ids])
            if uses_credits and values.credit_returns is not None
            else None
        ),
    )


def snapshot_groups(
    *,
    config: SimulationConfig,
    active: list[Student],
    students: list[Student],
    period: int,
    axis: Axis,
    values: Measurements,
    total_seats: int,
) -> tuple[GroupSnapshot, list[GroupSnapshot]]:
    """O agregado da universidade e o recorte do eixo, no mesmo instante.

    A contagem de concluintes sai de varrer `students`, não de um livro-caixa
    à parte: `graduated_at` só é preenchido ao fim do período, então uma
    varredura durante as rodadas de t dá exatamente "quem já se formou antes
    de t", e a mesma varredura depois delas dá "quem já se formou contando
    t". É a diferença que os dois instantes precisam, de graça — e sem um
    livro por eixo que pudesse divergir do estado real.
    """

    def take(
        group: str | None,
        members: list[Student],
        population: int,
        graduated: int,
        dismissed: int,
    ):
        return snapshot(
            group=group,
            members=members,
            # O calouro do período sai de toda média: ele não disputou nada.
            measured=[s for s in members if s.entry_period != period],
            values=values,
            total_seats=total_seats,
            population=population,
            graduated=graduated,
            dismissed=dismissed,
            uses_credits=config.uses_credits,
        )

    entered = [s for s in students if s.entry_period <= period]
    overall = take(
        None,
        active,
        len(entered),
        sum(1 for s in entered if s.graduated_at is not None),
        sum(1 for s in entered if s.dismissed_at is not None),
    )

    members: dict[str, list[Student]] = {key: [] for key in axis.order}
    for student in active:
        members[axis.key(student)].append(student)
    population = Counter(axis.key(s) for s in entered)
    graduated = Counter(axis.key(s) for s in entered if s.graduated_at is not None)
    dismissed = Counter(axis.key(s) for s in entered if s.dismissed_at is not None)
    return overall, [
        take(key, members[key], population[key], graduated[key], dismissed[key])
        for key in axis.order
    ]
