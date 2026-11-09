"""Uma alocação isolada, sem períodos: várias rodadas dos dois mecanismos.

A elegibilidade chega pronta — pré-requisito e disciplina de entrada não
entram. É a tela de depuração do mecanismo: o cenário é escrito à mão, e o que
se quer ver é como lance e ordenação tratam a *mesma* mensagem.

O bem é a **turma**, como na simulação: a vaga é dela, a utilidade é dela, e a
disciplina é o clique (eq. 5) — ninguém leva duas turmas da mesma. O lance é a
mochila em dois níveis de `behavior.compute_bids` e o pedido por CR lista as
turmas dentro da disciplina, exatamente como lá.

As contas são as mesmas da simulação (`equations/`); o que muda é que aqui não
há grade, histórico nem conclusão.

Cada aluno traz os dois eixos de **estratégia** — seletividade e concentração,
que são o `Behavior` com que ele decide — e a **disponibilidade**, que na
simulação é sorteada do perfil e aqui chega já realizada, em horas. Com ela o
fim do período é o mesmo: a mochila do que ele leva (`retained_set`) e a
exclusão do resto. É o que deixa ver a especulação em escala micro: quem pede
tudo e depois larga o que não cabe.

O que **não** entra do fechamento é o crédito: sem histórico, retorno e saldo
do período seguinte não têm onde aparecer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .auction import AuctionInput, Bid, run_auction
from .behavior import compute_bids
from .config import Mechanism
from .entities import Agent, Good, MutualExclusion
from .equations import (
    Behavior,
    available_goods,
    effective_load,
    grade_for_attempt,
    grade_shape,
    retained_set,
    stochastic_perturbations,
)
from .ranking import allocate_by_ranking, request_set


@dataclass(frozen=True)
class PlaygroundClass:
    """Uma turma — o bem alocado.

    `discipline` é o grupo dela; `None` é turma única, e aí a turma **é** a
    disciplina, com o mesmo nome — o mesmo caso particular de
    `SimulationConfig.classes_of`.
    """

    name: str
    seats: int
    hours: int
    discipline: str | None = None

    @property
    def group(self) -> str:
        return self.discipline if self.discipline is not None else self.name


@dataclass(frozen=True)
class PlaygroundStudent:
    id: str
    credits: int
    cr: float
    max_hours: int
    utilities: dict[str, float]
    eligible: tuple[str, ...]
    # δ, em horas e já realizada: no sandbox não há perfil de onde sorteá-la.
    # `None` é disponibilidade sem teto — ele leva tudo o que obteve.
    availability: float | None = None
    selectivity: float = 0.0
    concentration: float = 1.0

    @property
    def behavior(self) -> Behavior:
        return Behavior(
            concentration=self.concentration, selectivity=self.selectivity
        )


@dataclass(frozen=True)
class PlaygroundRoundStudent:
    id: str
    bids: dict[str, int]
    utilities: dict[str, float]
    won: tuple[str, ...]
    remaining_hours: int
    remaining_credits: int | None


@dataclass(frozen=True)
class PlaygroundRound:
    number: int
    prices: dict[str, int] | None
    students: tuple[PlaygroundRoundStudent, ...]


@dataclass(frozen=True)
class PlaygroundGrade:
    student_id: str
    name: str  # a turma cursada
    grade: float


@dataclass(frozen=True)
class PlaygroundClosing:
    """O fim do período de um aluno: o que ele levou e o que largou.

    `load` é Ŵ_a — `None` quando a disponibilidade não foi dada. As duas
    listas somam o que ele obteve nas rodadas, na ordem da grade.
    """

    student_id: str
    load: int | None
    retained: tuple[str, ...]
    excluded: tuple[str, ...]


@dataclass(frozen=True)
class PlaygroundResult:
    rounds: tuple[PlaygroundRound, ...]
    closing: tuple[PlaygroundClosing, ...]
    # Só do que foi retido: a excluída não recebe nota.
    grades: tuple[PlaygroundGrade, ...]


def normalized_utilities(utilities: dict[str, float]) -> dict[str, float]:
    """A linha do aluno reescalada para somar 1 — só para exibição.

    No cenário escrito à mão as utilidades chegam em qualquer escala, e a tela
    mostra frações. Nenhuma decisão depende disso: as duas mochilas comparam
    só razões.
    """
    total = sum(utilities.values())
    if total <= 0:
        return {}
    return {name: value / total for name, value in utilities.items()}


def _validate(
    classes: list[PlaygroundClass],
    students: list[PlaygroundStudent],
    rounds: int,
) -> None:
    if rounds < 1:
        raise ValueError("é preciso ao menos 1 rodada")
    if not classes:
        raise ValueError("o playground precisa de ao menos uma turma")
    if not students:
        raise ValueError("o playground precisa de ao menos um aluno")

    names = [c.name for c in classes]
    if len(set(names)) != len(names):
        raise ValueError("há turmas com nomes repetidos")
    ids = [s.id for s in students]
    if len(set(ids)) != len(ids) or any(not student_id.strip() for student_id in ids):
        raise ValueError("há alunos com identificadores repetidos ou vazios")

    known = set(names)
    for student in students:
        if student.max_hours < 1:
            raise ValueError(f"aluno {student.id!r}: carga horária máxima deve ser >= 1")
        if student.credits < 0:
            raise ValueError(f"aluno {student.id!r}: créditos devem ser >= 0")
        if student.availability is not None and not student.availability >= 0:
            raise ValueError(f"aluno {student.id!r}: CH disponível deve ser >= 0")
        if not student.selectivity >= 0:
            raise ValueError(f"aluno {student.id!r}: seletividade deve ser >= 0")
        if not math.isfinite(student.concentration):
            raise ValueError(f"aluno {student.id!r}: concentração deve ser finita")
        for name in student.eligible:
            if name not in known:
                raise ValueError(
                    f"aluno {student.id!r}: turma elegível inexistente {name!r}"
                )
            utility = student.utilities.get(name)
            if utility is None or utility <= 0:
                raise ValueError(
                    f"aluno {student.id!r}: utilidade de {name!r} deve ser um número positivo"
                )


@dataclass
class _Table:
    """O estado da mesa: oferta, saldos e o que cada um já levou."""

    seats: dict[str, int]
    hours: dict[str, int]
    capacity: dict[str, int]
    budget: dict[str, int]
    won: dict[str, set[str]]
    utilities: dict[str, dict[str, float]]
    # Turma -> disciplina, e o inverso, na ordem da oferta.
    groups: dict[str, str]
    classes: dict[str, tuple[str, ...]]

    def available(self, student_id: str) -> list[str]:
        """B_a^(r) — ver `equations.available_goods`: há vaga, cabe na carga e
        o aluno ainda não levou turma nenhuma da disciplina."""
        return available_goods(
            eligible=self.utilities[student_id],
            seats=self.seats,
            hours=self.hours,
            capacity=self.capacity[student_id],
            already_won=self.won[student_id],
            groups=self.groups,
        )

    def exclusions(self) -> list[MutualExclusion]:
        """Os cliques da eq. (5): um por disciplina de mais de uma turma."""
        return [
            MutualExclusion(frozenset(names))
            for names in self.classes.values()
            if len(names) > 1
        ]

    def grant(self, student_id: str, name: str) -> None:
        self.won[student_id].add(name)
        self.seats[name] -= 1
        self.capacity[student_id] -= self.hours[name]


def _auction_round(
    *,
    table: _Table,
    students: list[PlaygroundStudent],
    classes: list[PlaygroundClass],
    epsilon: dict[tuple[str, str], float],
    seed: int,
) -> tuple[dict[str, dict[str, int]], dict[str, list[str]], dict[str, int]]:
    """A rodada do leilão: lances, PLI, preço e consumo."""
    posted = {
        student.id: compute_bids(
            utilities=table.utilities[student.id],
            available=table.available(student.id),
            budget=table.budget[student.id],
            behavior=student.behavior,
            classes=table.classes,
        )
        for student in students
    }
    won_now: dict[str, list[str]] = {student.id: [] for student in students}
    prices = {c.name: 1 for c in classes if table.seats[c.name] > 0}

    bids = [
        Bid(student.id, name, credits)
        for student in students
        for name, credits in posted[student.id].items()
    ]
    if not bids:
        return posted, won_now, prices

    result = run_auction(
        AuctionInput(
            agents=[Agent(s.id, float(table.capacity[s.id])) for s in students],
            goods=[Good(c.name, table.seats[c.name], c.hours) for c in classes],
            exclusions=table.exclusions(),
            groups=table.groups,
            budgets=dict(table.budget),
            bids=bids,
            epsilon=epsilon,
            seed=seed,
        )
    )
    for (student_id, name), allocated in result.allocation.items():
        if allocated:
            won_now[student_id].append(name)
            table.grant(student_id, name)
    for (student_id, _name), consumed in result.consumption.items():
        table.budget[student_id] -= consumed
    for name, price in result.prices.items():
        if name in prices:
            prices[name] = price
    return posted, won_now, prices


def _ranking_round(
    *,
    table: _Table,
    students: list[PlaygroundStudent],
    epsilon: dict[tuple[str, str], float],
) -> tuple[dict[str, dict[str, int]], dict[str, list[str]]]:
    """A rodada da linha de base: pedido ordenado e ditadura serial."""
    requests: list[tuple[str, str]] = []
    posted: dict[str, dict[str, int]] = {}
    for student in students:
        asked = request_set(
            utilities=table.utilities[student.id],
            available=table.available(student.id),
            behavior=student.behavior,
            classes=table.classes,
        )
        posted[student.id] = {name: 1 for name in asked}
        requests.extend((student.id, name) for name in asked)

    won_now: dict[str, list[str]] = {student.id: [] for student in students}
    # A prioridade é do aluno; dentro dele quem ordena é a própria preferência,
    # que já veio na ordem de `requests`. A carga é verificada na concessão,
    # não no pedido.
    granted = allocate_by_ranking(
        requests=requests,
        priority={s.id: s.cr + epsilon.get((s.id, s.id), 0.0) for s in students},
        seats=table.seats,
        hours=table.hours,
        capacity={s.id: int(table.capacity[s.id]) for s in students},
        groups=table.groups,
    )
    for student_id, name in granted:
        won_now[student_id].append(name)
        table.grant(student_id, name)
    return posted, won_now


def _close(
    *,
    students: list[PlaygroundStudent],
    names: list[str],
    table: _Table,
) -> tuple[PlaygroundClosing, ...]:
    """A exclusão do fim do período — a mesma de `simulation.closing`.

    Valor = utilidade, peso = carga, teto = Ŵ_a. A utilidade é a crua da
    tela, sem normalizar: o argmax de uma soma não muda com a escala.
    """
    closing: list[PlaygroundClosing] = []
    for student in students:
        obtained = table.won[student.id]
        if student.availability is None:
            load = None
            kept = set(obtained)
        else:
            load = effective_load(availability=student.availability)
            kept = set(
                retained_set(
                    utilities=table.utilities[student.id],
                    hours=table.hours,
                    obtained=obtained,
                    load=load,
                )
            )
        closing.append(
            PlaygroundClosing(
                student_id=student.id,
                load=load,
                retained=tuple(name for name in names if name in kept),
                excluded=tuple(
                    name for name in names if name in obtained and name not in kept
                ),
            )
        )
    return tuple(closing)


def _grades(
    *,
    students: list[PlaygroundStudent],
    names: list[str],
    groups: dict[str, str],
    retained: dict[str, tuple[str, ...]],
    seed: int,
    mode_grade: float,
    zero_rate: float,
    max_rate: float,
) -> tuple[PlaygroundGrade, ...]:
    """As notas do que cada um cursou.

    O sandbox não guarda posição entre rodadas: sorteia um quantil por
    (aluno, disciplina) na hora, que é o bastante para a tela mostrar nota
    plausível. A simulação de verdade persiste o quantil, que é traço.

    O quantil é da **disciplina**, não da turma, como na simulação: o aluno
    não fica melhor por mudar de seção. E sai para **todo** par, cursado ou
    não: assim mexer na disponibilidade de um aluno não desloca o gerador e
    não muda a nota de ninguém mais.

    Todo mundo sai do mesmo perfil, em disciplina de dificuldade 1 e primeira
    tentativa — o sandbox é uma rodada isolada, e não tem histórico de onde
    tirar tentativa nem perfil por aluno.
    """
    disciplines = list(dict.fromkeys(groups[name] for name in names))
    column = {discipline: x for x, discipline in enumerate(disciplines)}
    rng = np.random.default_rng(seed)
    quantiles = rng.random((len(students), len(disciplines)))
    mode, left_sd, right_sd = grade_shape(
        mode_grade=mode_grade, zero_rate=zero_rate, max_rate=max_rate
    )
    grades: list[PlaygroundGrade] = []
    for a, student in enumerate(students):
        for name in names:
            if name not in retained[student.id]:
                continue
            grades.append(
                PlaygroundGrade(
                    student_id=student.id,
                    name=name,
                    grade=grade_for_attempt(
                        quantile=float(quantiles[a, column[groups[name]]]),
                        mode=mode,
                        left_sd=left_sd,
                        right_sd=right_sd,
                    ),
                )
            )
    return tuple(grades)


def run_playground(
    *,
    mechanism: Mechanism,
    rounds: int,
    seed: int,
    mode_grade: float = 8.0,
    zero_rate: float = 0.005,
    max_rate: float = 0.008,
    classes: list[PlaygroundClass],
    students: list[PlaygroundStudent],
) -> PlaygroundResult:
    _validate(classes, students, rounds)

    names = [c.name for c in classes]
    order = {name: index for index, name in enumerate(names)}
    groups = {c.name: c.group for c in classes}
    by_discipline: dict[str, list[str]] = {}
    for c in classes:
        by_discipline.setdefault(c.group, []).append(c.name)
    table = _Table(
        seats={c.name: c.seats for c in classes},
        hours={c.name: c.hours for c in classes},
        capacity={s.id: s.max_hours for s in students},
        budget={s.id: s.credits for s in students},
        won={s.id: set() for s in students},
        utilities={
            student.id: {
                name: student.utilities[name]
                for name in names
                if name in set(student.eligible)
            }
            for student in students
        },
        groups=groups,
        classes={group: tuple(names) for group, names in by_discipline.items()},
    )
    normalized = {
        student.id: normalized_utilities(table.utilities[student.id])
        for student in students
    }
    epsilon = stochastic_perturbations(
        [(student.id, name) for student in students for name in names],
        num_agents=len(students),
        num_goods=len(classes),
        seed=seed,
    )

    reports: list[PlaygroundRound] = []
    for number in range(1, rounds + 1):
        prices: dict[str, int] | None = None
        if mechanism == "credits":
            posted, won_now, prices = _auction_round(
                table=table,
                students=students,
                classes=classes,
                epsilon=epsilon,
                seed=seed,
            )
        else:
            posted, won_now = _ranking_round(
                table=table, students=students, epsilon=epsilon
            )

        reports.append(
            PlaygroundRound(
                number=number,
                prices=prices,
                students=tuple(
                    PlaygroundRoundStudent(
                        id=student.id,
                        bids=posted[student.id],
                        utilities=normalized[student.id],
                        won=tuple(sorted(won_now[student.id], key=lambda n: order[n])),
                        remaining_hours=table.capacity[student.id],
                        remaining_credits=(
                            table.budget[student.id] if mechanism == "credits" else None
                        ),
                    )
                    for student in students
                ),
            )
        )

    closing = _close(students=students, names=names, table=table)
    return PlaygroundResult(
        rounds=tuple(reports),
        closing=closing,
        grades=_grades(
            students=students,
            names=names,
            groups=groups,
            retained={row.student_id: row.retained for row in closing},
            seed=seed,
            mode_grade=mode_grade,
            zero_rate=zero_rate,
            max_rate=max_rate,
        ),
    )
