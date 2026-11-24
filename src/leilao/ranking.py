"""Linha de base: matrícula por ordenação de CR (Seção 7.3.1, eqs. 49-50).

É o mecanismo tradicional contra o qual o leilão é comparado. Nenhuma das
inovações propostas está presente: não há lance, orçamento nem preço. O que
substitui o orçamento é a carga horária — o aluno gasta W_a em horas, e gasta
tudo, porque hora não cursada não passa para o período seguinte. E ele a gasta
**em casa**: a restrição da eq. (4) é resolvida no pedido, antes da concessão,
que é a auto-restrição *ex-ante* que o leilão dispensa.

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
    hours: dict[str, int],
    capacity: int,
    behavior: Behavior = NEUTRAL,
    classes: dict[str, tuple[str, ...]] | None = None,
    conflicts: dict[str, tuple[str, ...]] | None = None,
    interest: float = 0.0,
) -> list[str]:
    """D_a^(t,r) — ver `equations.request_set`.

    A mensagem sai de `behavior.decide`, a mesma que o leilão usa: o que o CR
    faz com ela é cortar pela seletividade e resolver a mochila. O limiar que
    o leilão usa para parar o gasto não tem análogo aqui — lá não há
    investimento marginal que se interrompa.

    **Dois níveis.** O de fora é o corte da seletividade, sobre as
    **disciplinas**, igual ao do leilão: o grupo inteiro entra ou sai, e é por
    isso que o número de turmas não decide o que o aluno pede. O de dentro é a
    **mochila 0-1 com grafo de conflito** da eq. (50), direto sobre as turmas
    das disciplinas admitidas — carga e choque de horário na mesma tabela.

    Com `classes` ausente a grade é de turma única e os dois níveis coincidem;
    com `conflicts` ausente os cliques saem de `classes`, de modo que `M` vale
    sempre e `G` só quando o cenário declara horário.
    """
    groups, scores, _reserve = decide(
        utilities=utilities, behavior=behavior, classes=classes, interest=interest
    )
    if not classes:
        return rank_requests(
            utilities=groups,
            available=available,
            hours=hours,
            capacity=capacity,
            conflicts=conflicts,
        )

    # Só as turmas das disciplinas que passaram no corte: a seletividade é do
    # grupo, e a mochila escolhe entre turmas de grupos já admitidos.
    admitted = {name for discipline in groups for name in classes[discipline]}
    return rank_requests(
        utilities=scores,
        available=[name for name in available if name in admitted],
        hours=hours,
        capacity=capacity,
        conflicts=conflicts
        or {
            name: (discipline,)
            for discipline, names in classes.items()
            for name in names
        },
    )


def allocate_by_ilp(
    *,
    requests: list[tuple[str, str]],
    priority: dict[str, float],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: dict[str, int],
    conflicts: dict[str, tuple[str, ...]] | None = None,
    tiebreak: dict[str, float] | None = None,
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
    # Os cliques de `E` saem do mapa turma → grupos: é a mesma informação que
    # a varredura lê, na forma que a PLI precisa. Manter uma assinatura só
    # entre os dois alocadores é o que torna o eixo ordenação × PLI exato.
    cliques: dict[str, set[str]] = {}
    for name in seats:
        for group in (conflicts or {}).get(name, ()):
            cliques.setdefault(group, set()).add(name)
    problem = Problem(
        agents=[Agent(student_id, capacity[student_id]) for student_id in capacity],
        goods=[Good(name, seats[name], hours[name]) for name in seats],
        demands=[
            Demand(
                student_id,
                name,
                priority[student_id],
                (tiebreak or {}).get(student_id, 0.0),
            )
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
