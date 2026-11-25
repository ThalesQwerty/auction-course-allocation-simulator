"""O estado que anda dentro de um período letivo."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import SimulationConfig
from ..equations import guaranteed_share
from ..population import Student
from .reports import GUARANTEED_ROUND


@dataclass
class PeriodState:
    """Oferta, saldos e rastro de um período."""

    rounds: int
    config_seats: dict[str, int]
    seats: dict[str, int]
    capacity: dict[str, float]
    budget: dict[str, int]
    credits_start: dict[str, int]
    won: dict[str, set[str]] = field(default_factory=dict)
    won_round: dict[tuple[str, str], int] = field(default_factory=dict)
    paid: dict[tuple[str, str], int] = field(default_factory=dict)
    spent: dict[str, int] = field(default_factory=dict)
    bid_log: dict[str, dict[str, list[int]]] = field(default_factory=dict)
    bid_total: dict[str, int] = field(default_factory=dict)
    guaranteed: dict[str, list[str]] = field(default_factory=dict)
    granted: dict[str, int] = field(default_factory=dict)
    price_sum: dict[str, int] = field(default_factory=dict)
    price_rounds: dict[str, int] = field(default_factory=dict)

    @classmethod
    def opening(
        cls, *, config: SimulationConfig, active: list[Student]
    ) -> "PeriodState":
        config_seats = config.seats_by_class()
        names = list(config_seats)
        return cls(
            rounds=config.rounds,
            config_seats=config_seats,
            seats=dict(config_seats),
            capacity={s.id: float(config.max_hours) for s in active},
            budget={s.id: s.credits for s in active},
            credits_start={s.id: s.credits for s in active},
            won={s.id: set() for s in active},
            spent={s.id: 0 for s in active},
            bid_log={s.id: {} for s in active},
            bid_total={s.id: 0 for s in active},
            guaranteed={s.id: [] for s in active},
            granted=dict.fromkeys(names, 0),
            price_sum=dict.fromkeys(names, 0),
            price_rounds=dict.fromkeys(names, 0),
        )

    def record_bid(self, student_id: str, name: str, round_number: int, amount: int) -> None:
        """Anota o que o aluno pediu numa rodada. Zero nas que não pediu."""
        log = self.bid_log[student_id].setdefault(name, [0] * self.rounds)
        log[round_number - 1] = amount

    def grant(
        self, student_id: str, name: str, *, round_number: int, hours: dict[str, int]
    ) -> None:
        """Concede a vaga e desconta oferta e carga — eqs. (13) e (14)."""
        self.won[student_id].add(name)
        self.won_round[(student_id, name)] = round_number
        self.seats[name] -= 1
        self.capacity[student_id] -= hours[name]

    def charge(self, student_id: str, name: str, amount: int) -> None:
        """Desconta créditos do saldo e lança o pagamento — eq. (27)."""
        self.budget[student_id] -= amount
        self.spent[student_id] += amount
        self.paid[(student_id, name)] = self.paid.get((student_id, name), 0) + amount

    def requested(self, student_id: str) -> set[str]:
        """O que o aluno pediu no período: lance em alguma rodada, ou vaga"""
        asked = {name for name, log in self.bid_log[student_id].items() if any(log)}
        return asked | set(self.guaranteed[student_id])

    def enroll_newcomer(
        self,
        student_id: str,
        *,
        entry_courses: list[str],
        hours: dict[str, int],
        uses_credits: bool,
    ) -> None:
        """Matrícula garantida: vaga em todas as disciplinas de entrada, antes"""
        share = (
            guaranteed_share(
                budget=self.budget[student_id], entry_count=len(entry_courses)
            )
            if uses_credits
            else 0
        )
        marker = share if uses_credits else 1
        for name in entry_courses:
            self.guaranteed[student_id].append(name)
            self.grant(student_id, name, round_number=GUARANTEED_ROUND, hours=hours)
            self.granted[name] += 1
            self.charge(student_id, name, share)
            self.record_bid(student_id, name, 1, marker)
            self.bid_total[student_id] += share

    def messages(self) -> dict[str, dict[str, float]]:
        """A mensagem que o mecanismo recebeu até aqui, por aluno: créditos"""
        return {
            student_id: {name: float(sum(log)) for name, log in logs.items()}
            for student_id, logs in self.bid_log.items()
        }
