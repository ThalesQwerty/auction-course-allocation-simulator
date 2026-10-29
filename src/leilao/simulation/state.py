"""O estado que anda dentro de um período letivo.

Tudo o que as rodadas consomem e descontam vive aqui, num lugar só: as duas
alocações — leilão e ordenação — aplicam o resultado pelo mesmo método, e é
isso que garante que a contabilidade seja idêntica nos dois mecanismos.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import SimulationConfig
from ..equations import guaranteed_share
from ..population import Student
from .reports import GUARANTEED_ROUND


@dataclass
class PeriodState:
    """Oferta, saldos e rastro de um período.

    `seats` e `capacity` são descontados a cada vaga concedida (eqs. 13 e 14);
    `budget`, a cada crédito consumido (eq. 27). `config_seats` guarda a
    oferta original do período, que é sobre o que escassez e concorrência se
    medem — elas não andam entre as rodadas de propósito, porque descrevem o
    cenário que o aluno encontrou, não o que o leilão fez com ele.
    """

    rounds: int
    config_seats: dict[str, int]
    seats: dict[str, int]
    capacity: dict[str, float]  # W_a^(t,r)
    budget: dict[str, int]  # C_a^(t,r)
    credits_start: dict[str, int]  # C_a^(t,1), para o histórico e a oferta
    won: dict[str, set[str]] = field(default_factory=dict)
    won_round: dict[tuple[str, str], int] = field(default_factory=dict)
    paid: dict[tuple[str, str], int] = field(default_factory=dict)
    spent: dict[str, int] = field(default_factory=dict)
    # O que o aluno pediu em cada rodada. No leilão guarda c_{a,x}^(t,r); na
    # ordenação por CR não há lance, e guarda 1 onde houve solicitação — é o
    # marcador que a concorrência do período lê.
    bid_log: dict[str, dict[str, list[int]]] = field(default_factory=dict)
    # Créditos apostados no período, somando as rodadas. Acumula como o gasto,
    # para que as duas séries do mesmo gráfico falem do mesmo intervalo; a
    # diferença entre elas é o que foi apostado e não consumido.
    bid_total: dict[str, int] = field(default_factory=dict)
    guaranteed: dict[str, list[str]] = field(default_factory=dict)
    granted: dict[str, int] = field(default_factory=dict)
    price_sum: dict[str, int] = field(default_factory=dict)
    # Rodadas em que a disciplina ainda tinha vaga — o denominador do preço
    # médio dela (ver `equations.mean_price`).
    price_rounds: dict[str, int] = field(default_factory=dict)

    @classmethod
    def opening(
        cls, *, config: SimulationConfig, active: list[Student]
    ) -> "PeriodState":
        names = [d.name for d in config.disciplines]
        config_seats = {d.name: d.seats for d in config.disciplines}
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
        """O que o aluno pediu no período: lance em alguma rodada, ou vaga
        garantida.

        A matrícula garantida conta como pedido — o ingressante não disputou,
        mas ocupa a vaga, e para quem recursa a disciplina a pressão é a mesma.
        """
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
        """Matrícula garantida: vaga em todas as disciplinas de entrada, antes
        de o leilão abrir.

        O ingressante não dá lance. O sistema reparte o orçamento dele
        igualmente entre essas disciplinas e lança o gasto, ficando com o resto
        da divisão no saldo — é esse valor que o retorno de créditos (eq. 34)
        tem para trabalhar. A validação do cenário garante que a geração cabe
        na menor dessas ofertas e que a carga somada respeita W_a.

        A garantia vale só no ingresso: recursar uma dessas disciplinas é
        disputá-la no leilão como qualquer outra.
        """
        # Sem crédito não há o que lançar na conta: a vaga garantida é a mesma
        # nos dois mecanismos, e o que muda é só se ela custa algo.
        share = (
            guaranteed_share(
                budget=self.budget[student_id], entry_count=len(entry_courses)
            )
            if uses_credits
            else 0
        )
        # O marcador do `bid_log` é o que a concorrência do período lê. Na
        # linha de base ele é 1, porque não houve valor a lançar.
        marker = share if uses_credits else 1
        for name in entry_courses:
            self.guaranteed[student_id].append(name)
            self.grant(student_id, name, round_number=GUARANTEED_ROUND, hours=hours)
            self.granted[name] += 1
            self.charge(student_id, name, share)
            self.record_bid(student_id, name, 1, marker)
            self.bid_total[student_id] += share

    def messages(self) -> dict[str, dict[str, float]]:
        """A mensagem que o mecanismo recebeu até aqui, por aluno: créditos
        apostados no leilão, 1 por disciplina pedida na linha de base."""
        return {
            student_id: {name: float(sum(log)) for name, log in logs.items()}
            for student_id, logs in self.bid_log.items()
        }
