"""Uma rodada de alocação, nos dois mecanismos.

O que muda entre eles é **só o miolo**: o conjunto em que se pode obter vaga
(eq. 15) é o mesmo, a concessão desconta igual, e o registro é o mesmo. O que
difere é a mensagem que o aluno envia — créditos repartidos ou uma lista
ordenada — e quem decide a alocação.

É essa simetria que torna a diferença entre os dois lados atribuível ao
mecanismo, e não à contabilidade.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..auction import AuctionInput, Bid, run_auction
from ..behavior import compute_bids
from ..config import SimulationConfig
from ..entities import Agent, Good
from ..equations import Signals, available_goods, satisfaction
from ..population import Student
from ..ranking import allocate_by_ilp, allocate_by_ranking, request_set
from .reports import PriceStats
from .setup import Draws
from .state import PeriodState

# π_x quando não houve lance mal-sucedido — é o valor da eq. (24) nesse caso,
# inclusive quando o bem não recebeu lance nenhum e o leilão nem rodou.
PRICE_FLOOR = 1


@dataclass(frozen=True)
class RoundOutcome:
    """O que varia de uma rodada para a outra.

    O relatório de cada rodada só é montado depois do laço, quando a
    concorrência do período — que depende dos lances de *todas* as rodadas —
    já existe; até lá, o que varia fica guardado aqui.
    """

    number: int
    satisfaction: dict[str, float]
    won: dict[str, set[str]]  # o que foi ganho **nesta** rodada
    budget: dict[str, int]
    bids: dict[str, int]  # acumulado até aqui, como o gasto
    prices: PriceStats | None


def _available(
    *,
    active: list[Student],
    utilities: dict[str, dict[str, float]],
    state: PeriodState,
    hours: dict[str, int],
) -> dict[str, list[str]]:
    """B_a^(t,r) de cada aluno — ver `equations.available_goods`.

    O ingressante já conquistou tudo que lhe é elegível, então sai daqui
    vazio e não pede nada.
    """
    return {
        s.id: available_goods(
            eligible=utilities[s.id],
            seats=state.seats,
            hours=hours,
            capacity=state.capacity[s.id],
            already_won=state.won[s.id],
        )
        for s in active
    }


def _run_credit_round(
    *,
    config: SimulationConfig,
    draws: Draws,
    active: list[Student],
    utilities: dict[str, dict[str, float]],
    signals: Signals,
    state: PeriodState,
    available: dict[str, list[str]],
    round_number: int,
    won_now: dict[str, list[str]],
) -> dict[str, int]:
    """O leilão: lances, PLI (ou varredura), preço e consumo."""
    bids: list[Bid] = []
    for student in active:
        posted = compute_bids(
            utilities=utilities[student.id],
            available=available[student.id],
            budget=state.budget[student.id],
            behavior=student.behavior,
            signals=signals,
            catalogue=draws.catalogue,
        )
        for name, credits in posted.items():
            state.record_bid(student.id, name, round_number, credits)
        state.bid_total[student.id] += sum(posted.values())
        bids.extend(Bid(student.id, name, credits) for name, credits in posted.items())

    # Quem está no mercado nesta rodada, antes de a alocação consumir vaga:
    # só essas disciplinas têm preço com leitura. As vagas já entregues aos
    # ingressantes saíram do mercado antes da rodada 1.
    prices = {
        d.name: PRICE_FLOOR for d in config.disciplines if state.seats[d.name] > 0
    }
    if not bids:
        return prices

    result = run_auction(
        AuctionInput(
            agents=[Agent(s.id, state.capacity[s.id]) for s in active],
            goods=[
                Good(d.name, state.seats[d.name], d.hours) for d in config.disciplines
            ],
            budgets=state.budget,
            bids=bids,
            tie_break_order=draws.tie_break_order,
            epsilon=draws.epsilon,
            seed=config.seed,
        ),
        resolver=config.resolver,
    )
    for (student_id, name), allocated in result.allocation.items():
        if allocated:
            won_now[student_id].append(name)
            state.grant(student_id, name, round_number=round_number, hours=draws.hours)
    for (student_id, name), consumed in result.consumption.items():
        state.charge(student_id, name, consumed)
    for name, price in result.prices.items():
        if name in prices:
            prices[name] = price
    return prices


def _run_ranking_round(
    *,
    config: SimulationConfig,
    draws: Draws,
    active: list[Student],
    utilities: dict[str, dict[str, float]],
    grade_averages: dict[str, float],
    signals: Signals,
    state: PeriodState,
    available: dict[str, list[str]],
    round_number: int,
    won_now: dict[str, list[str]],
) -> None:
    """A linha de base: o aluno pede tudo que lhe é elegível, na própria ordem
    de preferência, e a restrição de carga (eq. 4) é resolvida pelo alocador.

    Não há lance, orçamento nem preço.
    """
    requests: list[tuple[str, str]] = []
    for student in active:
        for name in request_set(
            utilities=utilities[student.id],
            available=available[student.id],
            behavior=student.behavior,
            signals=signals,
            catalogue=draws.catalogue,
        ):
            state.record_bid(student.id, name, round_number, 1)
            requests.append((student.id, name))

    # A prioridade é do **aluno**, não do par: o mesmo CR vale em todas as
    # disciplinas que ele pediu. O ε desempata entre alunos; dentro de um
    # aluno quem ordena é a preferência dele, que já veio na ordem de
    # `requests`.
    priority = {
        s.id: grade_averages[s.id] + draws.epsilon.get((s.id, s.id), 0.0)
        for s in active
    }
    allocate = allocate_by_ilp if config.resolver == "ilp" else allocate_by_ranking
    for student_id, name in allocate(
        requests=requests,
        priority=priority,
        seats=state.seats,
        hours=draws.hours,
        capacity={s.id: int(state.capacity[s.id]) for s in active},
    ):
        won_now[student_id].append(name)
        state.grant(student_id, name, round_number=round_number, hours=draws.hours)


def run_round(
    *,
    config: SimulationConfig,
    draws: Draws,
    active: list[Student],
    utilities: dict[str, dict[str, float]],
    grade_averages: dict[str, float],
    signals: Signals,
    state: PeriodState,
    round_number: int,
) -> RoundOutcome:
    available = _available(
        active=active, utilities=utilities, state=state, hours=draws.hours
    )
    # A vaga garantida entra como conquista da rodada 1: é ali que ela passa a
    # valer, e sem isso o ingressante apareceria com satisfação zero na
    # primeira rodada e plena só no agregado do período.
    won_now: dict[str, list[str]] = {
        s.id: list(state.guaranteed[s.id]) if round_number == 1 else [] for s in active
    }

    prices: dict[str, int] | None = None
    if config.uses_credits:
        prices = _run_credit_round(
            config=config,
            draws=draws,
            active=active,
            utilities=utilities,
            signals=signals,
            state=state,
            available=available,
            round_number=round_number,
            won_now=won_now,
        )
    else:
        _run_ranking_round(
            config=config,
            draws=draws,
            active=active,
            utilities=utilities,
            grade_averages=grade_averages,
            signals=signals,
            state=state,
            available=available,
            round_number=round_number,
            won_now=won_now,
        )

    if prices is not None:
        for name, price in prices.items():
            state.price_sum[name] += price
            state.price_rounds[name] += 1

    return RoundOutcome(
        number=round_number,
        satisfaction={
            s.id: satisfaction(utilities=utilities[s.id], allocated=won_now[s.id])
            for s in active
        },
        won={s.id: set(won_now[s.id]) for s in active},
        budget=dict(state.budget),
        bids=dict(state.bid_total),
        # `None` fora do leilão: sem lance não se forma preço, e a série some
        # do gráfico em vez de virar uma linha de piso que ninguém pagou.
        prices=PriceStats.of(list(prices.values())) if prices is not None else None,
    )
