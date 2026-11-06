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

from .behavior import decide
from .entities import Agent, Demand, Good, MutualExclusion, Problem
from .equations import NEUTRAL, Behavior, serial_dictatorship
from .equations import request_set as rank_requests
from .wdp_solver import solve_wdp

__all__ = ["allocate_by_ilp", "allocate_by_ranking", "request_set"]

allocate_by_ranking = serial_dictatorship


def request_set(
    *,
    utilities: dict[str, float],
    available: list[str],
    behavior: Behavior = NEUTRAL,
    classes: dict[str, tuple[str, ...]] | None = None,
) -> list[str]:
    """D_a^(t,r) — ver `equations.request_set`.

    A mensagem sai de `behavior.decide`, a mesma que o leilão usa: o que o CR
    faz com ela é só ordenar. O limiar que o leilão usa para parar o gasto
    não tem análogo aqui — lá não há investimento marginal que se interrompa.

    **Ordenar as turmas com sinceridade é dominante** neste braço: turma
    recusada não custa nada e a prioridade do aluno não depende do que ele
    pede. É a mesma justificativa que a docstring de `equations.request_set`
    dá para disciplinas, um nível abaixo.

    E é por isso que aqui ele lista **todas** as turmas, enquanto no leilão
    aposta numa só (`equations.best_class`): lá cada crédito posto numa turma
    é um crédito que não está em outra, aqui não há nada a repartir. A
    assimetria é do mecanismo — mensagem cara contra mensagem gratuita —, a
    mesma que separa as duas mochilas um nível acima.
    """
    groups, scores, _reserve = decide(
        utilities=utilities, behavior=behavior, classes=classes
    )
    if not classes:
        return rank_requests(scores=groups, available=available)

    # **Dois níveis**: disciplinas na ordem de preferência e, dentro de
    # cada uma, as turmas na dela. Plana — todas as turmas misturadas — a
    # caminhada consumiria W_a em ordem de turma, e o braço passaria a
    # mudar *quais disciplinas* o aluno leva em vez de só qual turma.
    reachable = set(available)
    ordered = rank_requests(
        scores=groups,
        available=[
            discipline
            for discipline in groups
            if any(name in reachable for name in classes[discipline])
        ],
    )
    return [
        name
        for discipline in ordered
        for name in rank_requests(
            scores=scores,
            available=[n for n in classes[discipline] if n in reachable],
        )
    ]


def allocate_by_ilp(
    *,
    requests: list[tuple[str, str]],
    priority: dict[str, float],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: dict[str, int],
    groups: dict[str, str] | None = None,
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
    cliques: dict[str, set[str]] = {}
    if groups:
        for name, group in groups.items():
            if name in seats:
                cliques.setdefault(group, set()).add(name)
    problem = Problem(
        agents=[Agent(student_id, capacity[student_id]) for student_id in capacity],
        goods=[Good(name, seats[name], hours[name]) for name in seats],
        demands=[
            Demand(student_id, name, priority[student_id])
            for student_id, name in requests
        ],
        # O roteamento, deste lado, é a própria restrição de clique (eq. 5)
        # dentro da PLI — não a caminhada da ditadura serial. Os dois
        # mecanismos resolvem a mesma restrição com a máquina de cada um.
        exclusions=[
            MutualExclusion(frozenset(names))
            for names in cliques.values()
            if len(names) > 1
        ],
    )
    return [key for key, taken in solve_wdp(problem).items() if taken]
