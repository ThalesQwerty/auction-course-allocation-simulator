"""Como um instante da simulação vira linhas de relatório.

Dois recortes do mesmo instante: a universidade inteira e cada coorte. O
recorte **particiona** a população do agregado, então somá-lo reproduz
`overall` — é isso que permite trocar de agregação sem trocar de gráfico.

O eixo é genérico de propósito (`Axis`): um recorte novo é uma chave e uma
ordem. É assim que a coorte e os três eixos de quantil convivem.
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
    progress,
    request_states,
    semestralization,
    utilization,
    value_band,
    value_band_name,
    value_band_names,
)
from ..equations._mean import mean
from ..metrics import compute_metrics
from ..population import Student
from .reports import GroupSnapshot


# Separa o grupo espacial da coorte na chave de uma **célula** (ver
# `Axis.crossed`). A coorte vem por último e é sempre numérica, de modo que
# `rpartition` a recupera mesmo que o nome de um perfil traga o separador.
CELL_SEP = "|"

# O rótulo de quem **não está em faixa nenhuma** num eixo de estado: o aluno
# sem valor medido no instante. É o calouro, que não disputou nada, e é quem
# já saiu — formado ou jubilado — e portanto não tem CR corrente. Não é uma
# faixa: `snapshot_groups` o descarta em vez de somá-lo em algum lugar.
OUTSIDE = "\x00fora"


@dataclass(frozen=True)
class Axis:
    """Como rotular cada aluno e em que ordem as séries saem.

    A chave lê o aluno **e o instante**: um eixo de coorte só precisa do
    primeiro, mas um eixo de estado (`Axis.states`) rotula pelo valor medido
    agora, que não está no aluno.

    `partitions` diz se o eixo reparte a população **inteira** ou só quem foi
    medido. A coorte reparte: o aluno pertence à sua desde o ingresso e
    continua nela depois de sair, então as contagens de pessoas por coorte
    existem. Um eixo de estado não: formado e jubilado não têm CR corrente,
    nem reserva, nem saldo. Ali `population`, `graduated` e `dismissed` saem
    `None` — zeradas se leriam como "ninguém se formou", que é a mesma
    armadilha das grandezas de crédito no `ranking`.
    """

    key: Callable[[Student, "Measurements"], str]
    order: list[str]
    partitions: bool = True

    @classmethod
    def crossed(cls, spatial: "Axis", cohort: "Axis") -> "Axis":
        """O produto de um recorte espacial pela coorte — a **célula**.

        É a unidade de que as três réguas do eixo X saem: somando as células
        de um período dá a série por período, as de uma coorte dá a série por
        coorte, e as de mesma distância entre período e coorte dá a série por
        idade. **Não há eixo de idade**, e não falta: dentro de um período a
        idade e a coorte são a mesma partição (`idade = t − t_a`), e o que
        distingue as duas réguas é só como as células são reagrupadas ao
        longo do horizonte.

        Sem o cruzamento, a régua da idade só existiria no recorte "Geral" —
        e o ponto de escolher as duas coisas é justamente poder cruzá-las.

        A ordem é a do recorte espacial por fora e a da coorte por dentro,
        que é a ordem em que a tela lista os grupos.
        """
        return cls(
            key=lambda s, v: (
                OUTSIDE
                if spatial.key(s, v) == OUTSIDE
                else f"{spatial.key(s, v)}{CELL_SEP}{cohort.key(s, v)}"
            ),
            order=[
                f"{group}{CELL_SEP}{entry}"
                for group in spatial.order
                for entry in cohort.order
            ],
            partitions=spatial.partitions and cohort.partitions,
        )

    @classmethod
    def cohorts(cls, entry_periods: list[int], period: int) -> "Axis":
        """O eixo das coortes até o período corrente.

        Uma coorte só entra na lista depois do seu t_a, e nunca mais sai —
        nem quando esvazia na fase de drenagem, senão a série dela sumiria
        justamente quando termina de contar por onde cada um saiu.
        """
        return cls(
            key=lambda s, v: str(s.entry_period),
            order=[str(entry) for entry in entry_periods if entry <= period],
        )

    @classmethod
    def states(cls, config: SimulationConfig) -> dict[str, "Axis"]:
        """Os eixos de **estado**, cortados em faixas de valor corrente.

        Três grandezas que o sistema de fato lê: o CR, a utilidade de reserva
        e o orçamento de crédito. O corte é no valor de agora, com fronteira
        declarada pelo cenário — ver `equations.value_band` para por que a
        fronteira é fixa e a população é que se move.

        Houve, até 24/11/2026, três eixos de **quantil sobre o nível
        basilar** — desempenho, disponibilidade e seletividade. Eles
        respondiam outra pergunta ("o mecanismo trata melhor quem tem pouca
        aptidão?", com a mesma gente nos dois braços) e saíram junto com ela.
        O que fica é a função de resposta: o que acontece com quem chega com
        CR alto, venha ele de onde vier.

        O eixo do **crédito só existe no leilão**. No `ranking` não há moeda,
        então ele sai da lista inteiro em vez de sair zerado — e a interface
        omite as linhas e a legenda dele daquele lado.

        A disponibilidade não tem eixo aqui, e a falta é de propósito: o aluno
        não conhece a própria disponibilidade na hora de pedir (ver
        `availability`), então não há canal do mecanismo que possa responder a
        ela, e um eixo de estado sobre ela mediria o sorteio do semestre.
        """
        axes = {
            "grade_average": _state_axis(
                config, "grade_average", lambda v: v.grade_averages, decimals=1
            ),
            "reserve": _state_axis(
                config, "reserve", lambda v: v.reserves, decimals=3
            ),
        }
        if config.uses_credits:
            axes["credits"] = _state_axis(
                config, "credits", lambda v: v.supply, decimals=0
            )
        return axes


def _state_axis(
    config: SimulationConfig,
    axis: str,
    source: Callable[["Measurements"], dict[str, float]],
    *,
    decimals: int,
) -> Axis:
    """Um eixo de estado: rotula pelo valor medido, com os cortes do cenário.

    `source` é de onde o valor sai em `Measurements`. Quem não está lá não tem
    valor no instante e sai como `OUTSIDE` — ver a constante.
    """
    cuts = config.band_cuts(axis)
    low, high = config.band_domain(axis)
    order = value_band_names(cuts=cuts, low=low, high=high, decimals=decimals)

    def key(student: Student, values: "Measurements") -> str:
        measured = source(values)
        if student.id not in measured:
            return OUTSIDE
        return value_band_name(
            band=value_band(value=measured[student.id], cuts=cuts),
            cuts=cuts,
            low=low,
            high=high,
            decimals=decimals,
        )

    return Axis(key=key, order=order, partitions=False)


@dataclass(frozen=True)
class Measurements:
    """As grandezas por aluno de um instante, já calculadas.

    Todas indexadas por id. O que decide quem entra em cada média é
    `snapshot`, não este registro — aqui estão os valores de todo mundo.
    """

    satisfactions: dict[str, float]
    utilizations: dict[str, float]
    progresses: dict[str, float]
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
    # ψ sobre o **alocado**, antes da exclusão. `None` em plena rodada, onde
    # as duas leituras ainda são a mesma. O vão para `satisfactions` é a
    # dissipação — ver `equations.dissipation`.
    allocated_satisfactions: dict[str, float] | None
    # S_a^(t) — a seletividade do período, para a grade de correlações.
    selectivities: dict[str, float]
    # s_a^(t) — a utilidade de reserva (`equations.reserve_threshold`): a
    # seletividade já posta no bolo das elegíveis. É ela, e não `S`, que serve
    # de eixo de recorte e de correlação: `S` está na escala do interesse, que
    # a normalização da linha faz depender da grade, enquanto `s` é uma
    # participação em [0, 1) e é o limiar que a decisão de fato lê.
    reserves: dict[str, float]
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
    selectivities: dict[str, float] | None = None,
    reserves: dict[str, float] | None = None,
    allocated_satisfactions: dict[str, float] | None = None,
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
    approved = {s.id: s.approved(config.min_grade) for s in active}
    approved_hours = {
        student_id: sum(discipline_hours[name] for name in names)
        for student_id, names in approved.items()
    }
    # O progresso separa as duas parcelas porque a conclusão as exige
    # diferente: a obrigatória inteira, a optativa só até X.
    elective_hours_of = config.elective_hours_by_discipline()
    approved_elective_hours = {
        student_id: sum(
            discipline_hours[name] for name in names if name in elective_hours_of
        )
        for student_id, names in approved.items()
    }
    # W_obg e X sao do cenario, nao do aluno: uma conta so para todo mundo.
    required_hours = sum(
        discipline_hours[name] for name in config.required_disciplines()
    )
    # Turma → disciplina, uma vez: os seis estados são por disciplina.
    discipline_of = config.discipline_by_class()
    return Measurements(
        satisfactions=satisfactions,
        # Aproveitamento sai de `won`, e não da carga aprovada, porque mede
        # alocação e não desempenho: a disciplina conta assim que a vaga é
        # obtida, reprove o aluno nela ou não.
        utilizations={
            s.id: utilization(won=won[s.id], hours=hours, max_hours=config.max_hours)
            for s in active
        },
        # O progresso, ao contrario, sai do **historico**: e o que fecha a
        # grade sobre a carga que a grade pede, e por isso e a unica grandeza
        # por aluno daqui que nao zera no comeco do periodo. Chegar a 1 e
        # exatamente concluir o curso.
        progresses={
            s.id: progress(
                approved_required_hours=approved_hours[s.id]
                - approved_elective_hours[s.id],
                approved_elective_hours=approved_elective_hours[s.id],
                required_hours=required_hours,
                elective_hours_needed=config.elective_hours,
            )
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
                    # O estado é da **disciplina**: o que o aluno pediu e
                    # levou vem por turma e é dobrado no grupo dela.
                    groups=discipline_of,
                )
                for s in active
            }
            if retained is not None and requested is not None
            else None
        ),
        allocated_satisfactions=allocated_satisfactions,
        selectivities=selectivities or {s.id: 0.0 for s in active},
        reserves=reserves or {s.id: 0.0 for s in active},
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
    population: int | None,
    graduated: int | None,
    dismissed: int | None,
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
            mean_credits_spent=None,
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
            progresses=pick(values.progresses),
            fidelities=pick(values.fidelities),
            grade_averages=pick(values.grade_averages),
            semestralizations=pick(values.semestralizations),
            scarcities=pick(values.scarcities),
            contentions=pick(values.contentions),
            allocated=sum(len(values.won[i]) for i in ids),
            total_seats=total_seats,
            reserves=pick(values.reserves),
            # A oferta é `None` onde não há moeda, e é só isso que apaga a
            # linha de crédito da grade de correlações.
            supplies=pick(values.supply) if uses_credits else None,
            allocated_satisfactions=(
                pick(values.allocated_satisfactions)
                if values.allocated_satisfactions is not None
                else None
            ),
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
        # O gasto não precisa de medição própria: é a oferta de abertura
        # menos o que sobrou, que é exatamente o consumo da eq. (25)
        # acumulado até aqui. Derivar em vez de propagar mantém as duas
        # pontas impossíveis de divergir.
        mean_credits_spent=in_credits(
            (supply - sum(values.credits[i] for i in ids)) / len(ids)
        ),
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

    def measured_of(students_: list[Student]) -> list[Student]:
        """O calouro do período sai de toda média: ele não disputou nada."""
        return [s for s in students_ if s.entry_period != period]

    def take(
        group: str | None,
        members: list[Student],
        population: int | None,
        graduated: int | None,
        dismissed: int | None,
    ):
        return snapshot(
            group=group,
            members=members,
            measured=measured_of(members),
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
        # Num eixo de estado o calouro fica de fora: ele não disputou nada, e o
        # CR 0 dele é ausência de medida, não medida de 0 — somá-lo empilharia
        # toda a coorte de entrada na faixa mais baixa. Num eixo que reparte a
        # população ele continua contando, como manda `GroupSnapshot`.
        labelled = active if axis.partitions else measured_of(active)
        for student in labelled:
            label = axis.key(student, values)
            if label in members:
                members[label].append(student)
        if not axis.partitions:
            # As contagens de pessoas não existem por faixa de estado — ver
            # `Axis.partitions`.
            return [take(key, members[key], None, None, None) for key in axis.order]
        population = Counter(axis.key(s, values) for s in entered)
        graduated = Counter(
            axis.key(s, values) for s in entered if s.graduated_at is not None
        )
        dismissed = Counter(
            axis.key(s, values) for s in entered if s.dismissed_at is not None
        )
        return [
            take(key, members[key], population[key], graduated[key], dismissed[key])
            for key in axis.order
        ]

    return overall, {name: split(axis) for name, axis in axes.items()}
