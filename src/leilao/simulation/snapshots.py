"""Como um instante da simulação vira linhas de relatório.

Dois recortes do mesmo instante: a universidade inteira e cada coorte. O
recorte **particiona** a população do agregado, então somá-lo reproduz
`overall` — é isso que permite trocar de agregação sem trocar de gráfico.

O eixo é genérico de propósito (`Axis`): um recorte novo é uma chave e uma
ordem. É assim que a coorte e os quatro eixos de perfil convivem.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from ..config import SimulationConfig
from ..equations import (
    RequestStates,
    credits_per_seat,
    message_fidelity,
    request_states,
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
        """O eixo das coortes até o período corrente.

        Uma coorte só entra na lista depois do seu t_a, e nunca mais sai —
        nem quando esvazia na fase de drenagem, senão a série dela sumiria
        justamente quando termina de contar por onde cada um saiu.
        """
        return cls(
            key=lambda s: str(s.entry_period),
            order=[str(entry) for entry in entry_periods if entry <= period],
        )

    @classmethod
    def profiles(cls, config: SimulationConfig) -> dict[str, "Axis"]:
        """Os quatro eixos de perfil, na ordem em que o cenário os declara.

        Ao contrário da coorte, a lista não depende do período: o grupo existe
        desde o primeiro ingresso, e um recorte vazio sai com métrica `None`,
        como qualquer outro.
        """
        return {
            "performance": cls(
                key=lambda s: s.performance.name,
                order=[p.name for p in config.performance_profiles],
            ),
            "availability": cls(
                key=lambda s: s.availability.name,
                order=[p.name for p in config.availability_profiles],
            ),
            "selectivity": cls(
                key=lambda s: s.selectivity.name,
                order=[p.name for p in config.selectivity_profiles],
            ),
            "concentration": cls(
                key=lambda s: s.concentration.name,
                order=[p.name for p in config.concentration_profiles],
            ),
        }


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
    # O que o aluno largou e o aproveitamento do que ficou. `None` em plena
    # rodada: a exclusão acontece depois da última, então só o recorte de fim
    # de período tem o que contar.
    excluded: dict[str, list[str]] | None
    effective_utilizations: dict[str, float] | None
    request_states: dict[str, RequestStates] | None
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
    hours: dict[str, int],  # por turma: pesa o que foi alocado
    discipline_hours: dict[str, int],  # por disciplina: pesa o histórico
    credit_returns: dict[str, int] | None,
    retained: dict[str, set[str]] | None = None,
    excluded: dict[str, list[str]] | None = None,
    requested: dict[str, set[str]] | None = None,
) -> Measurements:
    """Calcula as grandezas que dependem do instante.

    `ages` vem do chamador porque acompanha o instante do recorte: nas
    rodadas de t o aluno completou t − t_a períodos; ao fim de t, um a mais —
    e é esse intervalo que a carga aprovada do mesmo recorte cobre.

    `retained` e `excluded` só existem no recorte de fim de período, pelo
    mesmo motivo que `credit_returns`: a exclusão é posterior à última rodada.
    """
    # A carga aprovada é do **histórico**, que é por disciplina: o aluno
    # aprovou a matéria, não a seção em que a cursou.
    approved_hours = {
        s.id: s.approved_hours(discipline_hours, config.min_grade) for s in active
    }
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
        excluded=excluded,
        # O aproveitamento *efetivo*: só a carga que ele de fato levou. Lido
        # contra `utilizations`, o vão entre os dois é o desperdício.
        effective_utilizations=(
            {
                s.id: utilization(
                    won=retained[s.id], hours=hours, max_hours=config.max_hours
                )
                for s in active
            }
            if retained is not None
            else None
        ),
        # Os seis estados só fecham depois da exclusão e das notas — ver
        # `equations.request_states`. `approved` é o acumulado ao fim do
        # período; `utilities` traz o elegível do início dele.
        request_states=(
            {
                s.id: request_states(
                    catalogue=[d.name for d in config.disciplines],
                    approved=s.approved(config.min_grade),
                    eligible=utilities[s.id],
                    requested=requested[s.id],
                    won=won[s.id],
                    retained=retained[s.id],
                )
                for s in active
            }
            if retained is not None and requested is not None
            else None
        ),
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
    """Um recorte qualquer: a universidade inteira ou uma coorte.

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
            excluded=(
                sum(len(values.excluded[i]) for i in ids)
                if values.excluded is not None
                else None
            ),
            effective_utilizations=(
                pick(values.effective_utilizations)
                if values.effective_utilizations is not None
                else None
            ),
            states=(
                [values.request_states[i] for i in ids]
                if values.request_states is not None
                else None
            ),
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
    axes: dict[str, Axis],
    values: Measurements,
    total_seats: int,
) -> tuple[GroupSnapshot, dict[str, list[GroupSnapshot]]]:
    """O agregado da universidade e o recorte de cada eixo, no mesmo instante.

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

    def split(axis: Axis) -> list[GroupSnapshot]:
        members: dict[str, list[Student]] = {key: [] for key in axis.order}
        for student in active:
            members[axis.key(student)].append(student)
        population = Counter(axis.key(s) for s in entered)
        graduated = Counter(axis.key(s) for s in entered if s.graduated_at is not None)
        dismissed = Counter(axis.key(s) for s in entered if s.dismissed_at is not None)
        return [
            take(key, members[key], population[key], graduated[key], dismissed[key])
            for key in axis.order
        ]

    return overall, {name: split(axis) for name, axis in axes.items()}
