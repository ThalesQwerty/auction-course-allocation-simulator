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
from .equations import NEUTRAL, Behavior, best_class, serial_dictatorship
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

    **Ordenar com sinceridade é dominante** neste braço: pedido recusado não
    custa nada e a prioridade do aluno não depende do que ele pede. É a mesma
    justificativa que a docstring de `equations.request_set` dá.

    **Dois níveis**, como no leilão. De fora, as disciplinas na ordem de
    preferência; de dentro, **uma turma por disciplina** — a melhor
    disponível (`equations.best_class`). Aqui o aluno escolhe a seção em que
    quer se matricular, e o pedido é por ela: pedir duas turmas da mesma
    disciplina seria pedir duas vezes a mesma vaga, e o clique da eq. (5)
    reduziria o par a uma delas de todo modo.

    É aí que a assimetria com o leilão aparece, e ela é do mecanismo: lá o
    nível de dentro é **outra mochila côncava**, porque há *quanto* a dizer e
    o aluno reparte a fatia da disciplina entre as turmas dela. Aqui só há
    *qual*, e o aluno diz a melhor. Perdida ela na rodada 1,
    `available_goods` devolve as irmãs na rodada 2.
    """
    groups, scores, _reserve = decide(
        utilities=utilities, behavior=behavior, classes=classes
    )
    if not classes:
        return rank_requests(scores=groups, available=available)

    reachable = set(available)
    open_classes = {
        discipline: [name for name in classes[discipline] if name in reachable]
        for discipline in groups
    }
    ordered = rank_requests(
        scores=groups,
        available=[d for d, names in open_classes.items() if names],
    )
    chosen = (
        best_class(scores=scores, available=open_classes[discipline])
        for discipline in ordered
    )
    return [name for name in chosen if name is not None]


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
