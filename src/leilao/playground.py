"""Uma alocação isolada, sem períodos: várias rodadas dos dois mecanismos.

A elegibilidade chega pronta — pré-requisito e disciplina de entrada não
entram. É a tela de depuração do mecanismo: o cenário é escrito à mão, e o que
se quer ver é como lance e ordenação tratam a *mesma* mensagem.

As contas são as mesmas da simulação (`equations/`); o que muda é que aqui não
há grade, histórico nem conclusão.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .auction import AuctionInput, Bid, run_auction
from .behavior import compute_bids
from .config import Mechanism
from .entities import Agent, Good
from .equations import APTITUDE_GUARD, grade_for_attempt, stochastic_perturbations
from .ranking import allocate_by_ranking, request_set


@dataclass(frozen=True)
class PlaygroundDiscipline:
    name: str
    seats: int
    hours: int


@dataclass(frozen=True)
class PlaygroundStudent:
    id: str
    credits: int
    cr: float
    max_hours: int
    utilities: dict[str, float]
    eligible: tuple[str, ...]


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
    discipline: str
    grade: float


@dataclass(frozen=True)
class PlaygroundResult:
    rounds: tuple[PlaygroundRound, ...]
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
    disciplines: list[PlaygroundDiscipline],
    students: list[PlaygroundStudent],
    rounds: int,
) -> None:
    if rounds < 1:
        raise ValueError("é preciso ao menos 1 rodada")
    if not disciplines:
        raise ValueError("o playground precisa de ao menos uma disciplina")
    if not students:
        raise ValueError("o playground precisa de ao menos um aluno")

    names = [d.name for d in disciplines]
    if len(set(names)) != len(names):
        raise ValueError("há disciplinas com nomes repetidos")
    ids = [s.id for s in students]
    if len(set(ids)) != len(ids) or any(not student_id.strip() for student_id in ids):
        raise ValueError("há alunos com identificadores repetidos ou vazios")

    known = set(names)
    for student in students:
        if student.max_hours < 1:
            raise ValueError(f"aluno {student.id!r}: carga horária máxima deve ser >= 1")
        if student.credits < 0:
            raise ValueError(f"aluno {student.id!r}: créditos devem ser >= 0")
        for name in student.eligible:
            if name not in known:
                raise ValueError(
                    f"aluno {student.id!r}: disciplina elegível inexistente {name!r}"
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

    def available(self, student_id: str) -> list[str]:
        """B_a^(r): há vaga, cabe na carga e o aluno ainda não a conquistou."""
        return [
            name
            for name in self.utilities[student_id]
            if self.seats[name] > 0
            and self.hours[name] <= self.capacity[student_id]
            and name not in self.won[student_id]
        ]

    def grant(self, student_id: str, name: str) -> None:
        self.won[student_id].add(name)
        self.seats[name] -= 1
        self.capacity[student_id] -= self.hours[name]


def _auction_round(
    *,
    table: _Table,
    students: list[PlaygroundStudent],
    disciplines: list[PlaygroundDiscipline],
    epsilon: dict[tuple[str, str], float],
    seed: int,
) -> tuple[dict[str, dict[str, int]], dict[str, list[str]], dict[str, int]]:
    """A rodada do leilão: lances, PLI, preço e consumo."""
    posted = {
        student.id: compute_bids(
            utilities=table.utilities[student.id],
            available=table.available(student.id),
            budget=table.budget[student.id],
        )
        for student in students
    }
    won_now: dict[str, list[str]] = {student.id: [] for student in students}
    prices = {d.name: 1 for d in disciplines if table.seats[d.name] > 0}

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
            goods=[Good(d.name, table.seats[d.name], d.hours) for d in disciplines],
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
    )
    for student_id, name in granted:
        won_now[student_id].append(name)
        table.grant(student_id, name)
    return posted, won_now


def _grades(
    *,
    students: list[PlaygroundStudent],
    names: list[str],
    won: dict[str, set[str]],
    seed: int,
    aptitude_alpha: float,
    aptitude_beta: float,
) -> tuple[PlaygroundGrade, ...]:
    """As notas do que cada um levou.

    O sandbox não guarda aptidão entre rodadas: sorteia uma por
    (aluno, disciplina) na hora, que é o bastante para a tela mostrar nota
    plausível. A simulação de verdade persiste a aptidão, que é traço.
    """
    rng = np.random.default_rng(seed)
    grades: list[PlaygroundGrade] = []
    for student in students:
        for name in names:
            if name not in won[student.id]:
                continue
            aptitude = float(
                np.clip(
                    rng.beta(aptitude_alpha, aptitude_beta),
                    APTITUDE_GUARD,
                    1.0 - APTITUDE_GUARD,
                )
            )
            grades.append(
                PlaygroundGrade(
                    student_id=student.id,
                    discipline=name,
                    grade=grade_for_attempt(
                        aptitude=aptitude,
                        difficulty=1.0,
                        relative_utility=1.0,
                        attempt=1,
                        utility_gain=0.0,
                        retake_gain=1.0,
                    ),
                )
            )
    return tuple(grades)


def run_playground(
    *,
    mechanism: Mechanism,
    rounds: int,
    seed: int,
    aptitude_alpha: float = 4.0,
    aptitude_beta: float = 2.0,
    disciplines: list[PlaygroundDiscipline],
    students: list[PlaygroundStudent],
) -> PlaygroundResult:
    _validate(disciplines, students, rounds)

    names = [d.name for d in disciplines]
    order = {name: index for index, name in enumerate(names)}
    table = _Table(
        seats={d.name: d.seats for d in disciplines},
        hours={d.name: d.hours for d in disciplines},
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
    )
    normalized = {
        student.id: normalized_utilities(table.utilities[student.id])
        for student in students
    }
    epsilon = stochastic_perturbations(
        [(student.id, name) for student in students for name in names],
        num_agents=len(students),
        num_goods=len(disciplines),
        seed=seed,
    )

    reports: list[PlaygroundRound] = []
    for number in range(1, rounds + 1):
        prices: dict[str, int] | None = None
        if mechanism == "credits":
            posted, won_now, prices = _auction_round(
                table=table,
                students=students,
                disciplines=disciplines,
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

    return PlaygroundResult(
        rounds=tuple(reports),
        grades=_grades(
            students=students,
            names=names,
            won=table.won,
            seed=seed,
            aptitude_alpha=aptitude_alpha,
            aptitude_beta=aptitude_beta,
        ),
    )
