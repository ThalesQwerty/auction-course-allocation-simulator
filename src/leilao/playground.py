"""Uma alocação, sem períodos: várias rodadas dos dois mecanismos.

A elegibilidade chega pronta. Pré-requisito e disciplina de entrada não entram.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .auction import AuctionInput, Bid, run_auction
from .behavior import compute_bids
from .config import Mechanism
from .entities import Agent, Good
from .grading import grade_for_attempt
from .ranking import allocate_by_ranking, request_set
from .tie_breaking import stochastic_perturbations


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
    total = sum(utilities.values())
    if total <= 0:
        return {}
    return {name: value / total for name, value in utilities.items()}


def run_playground(
    *,
    mechanism: Mechanism,
    rounds: int,
    seed: int,
    grade_mean: float,
    grade_stddev: float,
    disciplines: list[PlaygroundDiscipline],
    students: list[PlaygroundStudent],
) -> PlaygroundResult:
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
                raise ValueError(f"aluno {student.id!r}: disciplina elegível inexistente {name!r}")
            utility = student.utilities.get(name)
            if utility is None or utility <= 0:
                raise ValueError(
                    f"aluno {student.id!r}: utilidade de {name!r} deve ser um número positivo"
                )

    seats = {d.name: d.seats for d in disciplines}
    hours = {d.name: d.hours for d in disciplines}
    capacity = {s.id: s.max_hours for s in students}
    budget = {s.id: s.credits for s in students}
    won: dict[str, set[str]] = {s.id: set() for s in students}
    cr = {s.id: s.cr for s in students}
    utilities = {
        student.id: {
            name: student.utilities[name]
            for name in names
            if name in set(student.eligible)
        }
        for student in students
    }
    normalized = {
        student.id: normalized_utilities(utilities[student.id]) for student in students
    }
    epsilon = stochastic_perturbations(
        [(student.id, name) for student in students for name in names],
        num_agents=len(students),
        num_goods=len(disciplines),
        seed=seed,
    )

    round_reports: list[PlaygroundRound] = []
    for round_number in range(1, rounds + 1):
        available = {
            student.id: [
                name
                for name in utilities[student.id]
                if seats[name] > 0
                and hours[name] <= capacity[student.id]
                and name not in won[student.id]
            ]
            for student in students
        }
        posted: dict[str, dict[str, int]] = {student.id: {} for student in students}
        won_now: dict[str, list[str]] = {student.id: [] for student in students}
        prices: dict[str, int] | None = None

        if mechanism == "credits":
            bids: list[Bid] = []
            for student in students:
                student_bids = compute_bids(
                    utilities=utilities[student.id],
                    available=available[student.id],
                    budget=budget[student.id],
                )
                posted[student.id] = student_bids
                bids.extend(
                    Bid(student.id, name, credits) for name, credits in student_bids.items()
                )
            offered = [name for name in names if seats[name] > 0]
            prices = {name: 1 for name in offered}
            if bids:
                result = run_auction(
                    AuctionInput(
                        agents=[Agent(student.id, float(capacity[student.id])) for student in students],
                        goods=[Good(d.name, seats[d.name], d.hours) for d in disciplines],
                        budgets=dict(budget),
                        bids=bids,
                        epsilon=epsilon,
                        seed=seed,
                    )
                )
                for (student_id, name), allocated in result.allocation.items():
                    if allocated:
                        won_now[student_id].append(name)
                        won[student_id].add(name)
                        seats[name] -= 1
                        capacity[student_id] -= hours[name]
                for (student_id, _name), consumed in result.consumption.items():
                    budget[student_id] -= consumed
                for name, price in result.prices.items():
                    if name in prices:
                        prices[name] = price
        else:
            requests: list[tuple[str, str]] = []
            for student in students:
                asked = request_set(
                    utilities=utilities[student.id],
                    available=available[student.id],
                    hours=hours,
                    capacity=capacity[student.id],
                )
                posted[student.id] = {name: 1 for name in asked}
                requests.extend((student.id, name) for name in asked)
            priority = {key: cr[key[0]] + epsilon.get(key, 0.0) for key in requests}
            for student_id, name in allocate_by_ranking(
                requests=requests, priority=priority, seats=seats
            ):
                won_now[student_id].append(name)
                won[student_id].add(name)
                seats[name] -= 1
                capacity[student_id] -= hours[name]

        order = {name: index for index, name in enumerate(names)}
        round_reports.append(
            PlaygroundRound(
                number=round_number,
                prices=prices,
                students=tuple(
                    PlaygroundRoundStudent(
                        id=student.id,
                        bids=posted[student.id],
                        utilities=normalized[student.id],
                        won=tuple(sorted(won_now[student.id], key=lambda name: order[name])),
                        remaining_hours=capacity[student.id],
                        remaining_credits=budget[student.id] if mechanism == "credits" else None,
                    )
                    for student in students
                ),
            )
        )

    rng = np.random.default_rng(seed)
    grades: list[PlaygroundGrade] = []
    for student in students:
        for name in names:
            if name not in won[student.id]:
                continue
            drawn = float(rng.normal(grade_mean, grade_stddev))
            grades.append(
                PlaygroundGrade(
                    student_id=student.id,
                    discipline=name,
                    grade=grade_for_attempt(drawn, 1, 0.0),
                )
            )

    return PlaygroundResult(rounds=tuple(round_reports), grades=tuple(grades))
