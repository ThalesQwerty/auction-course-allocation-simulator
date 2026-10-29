"""Linha de base: matrícula por ordenação de CR (Seção 7.3.1, eqs. 49-50).

É o mecanismo tradicional contra o qual o leilão é comparado. Nenhuma das
inovações propostas está presente: não há lance, orçamento nem preço. O que
substitui o orçamento é a carga horária — o aluno gasta W_a em horas, e gasta
tudo, porque hora não cursada não passa para o período seguinte.

A diferença de fundo entre os dois mecanismos é **o que o aluno consegue
dizer**. Aqui ele diz um *conjunto ordenado*: a utilidade só ordena. No
leilão ele diz *quanto* cada disciplina vale, repartindo créditos com retorno
decrescente. Essa é a expressividade que a comparação mede.

As peças são três, e cada uma tem arquivo próprio em `equations/`:
`request_set` (o que o aluno pede, eq. 50), `serial_dictatorship` (o que a
universidade concede) e `grade_average` (a prioridade, eq. 49).
"""
from __future__ import annotations

from .entities import Agent, Demand, Good, Problem
from .equations import NEUTRAL, Behavior, Signals, decision_scores, serial_dictatorship
from .equations import request_set as rank_requests
from .wdp_solver import solve_wdp

__all__ = ["allocate_by_ilp", "allocate_by_ranking", "request_set"]

allocate_by_ranking = serial_dictatorship


def request_set(
    *,
    utilities: dict[str, float],
    available: list[str],
    behavior: Behavior = NEUTRAL,
    signals: Signals | None = None,
    catalogue: int = 0,
) -> list[str]:
    """D_a^(t,r) — ver `equations.request_set`."""
    return rank_requests(
        scores=decision_scores(
            utilities=utilities,
            behavior=behavior,
            signals=signals,
            catalogue=catalogue,
        ),
        available=available,
        reserve=behavior.reserve,
    )


def allocate_by_ilp(
    *,
    requests: list[tuple[str, str]],
    priority: dict[str, float],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: dict[str, int],
) -> list[tuple[str, str]]:
    """A mesma linha de base, resolvida globalmente: maximiza a soma dos CRs
    atendidos sujeito às vagas (eq. 3) e à carga de cada aluno (eq. 4).

    É a célula "CR × PLI" do 2×2, e usa **o mesmo resolvedor do leilão** — só
    muda o peso da preferência, que ali é o lance e aqui é o CR. Isso torna o
    eixo exato por construção: nada além do resolvedor difere entre as células
    de uma linha.

    **Um defeito a declarar**, e ele é do mecanismo, não da implementação:
    como todas as demandas de um aluno têm o mesmo peso N_a, a PLI é
    indiferente sobre *qual* dos pedidos dele cortar quando a carga aperta, e
    usa essa liberdade para liberar vaga aos outros. O aluno não tem voz sobre
    o que perde — ao contrário da ditadura serial, em que ele perde o que
    menos queria. É a diferença entre tratar o CR como fila e como peso.
    """
    if not requests:
        return []
    problem = Problem(
        agents=[Agent(student_id, capacity[student_id]) for student_id in capacity],
        goods=[Good(name, seats[name], hours[name]) for name in seats],
        demands=[
            Demand(student_id, name, priority[student_id])
            for student_id, name in requests
        ],
    )
    return [key for key, taken in solve_wdp(problem).items() if taken]
