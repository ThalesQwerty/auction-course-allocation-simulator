"""Linha de base: matrícula por ordenação de CR (Seção 7.3.1, eqs. 49-50).

É o mecanismo tradicional, contra o qual o leilão por créditos é comparado.
Nenhuma das inovações propostas está presente: não há lance, não há orçamento
de créditos, não há preço e o resolvedor não usa PLI. A alocação é uma
**varredura**: todas as solicitações do período são ordenadas pelo CR de quem
as fez, e cada uma recebe a vaga se ainda houver.

A diferença de fundo entre os dois mecanismos está em *onde* as restrições são
resolvidas. No leilão, carga horária e exclusão mútua entram como restrições do
PLI, e é o resolvedor global que as satisfaz. Aqui elas são resolvidas
**localmente e ex-ante** por cada aluno, dentro das próprias solicitações: o
aluno só pede um conjunto que já lhe cabe, e por isso atender todos os pedidos
dele é sempre viável. A varredura não precisa reverificar nada.

O que substitui o orçamento é a carga horária. No leilão o aluno reparte
C_a^(t,r) entre as disciplinas; aqui ele gasta W_a^(t,r) em horas, e gasta tudo,
porque hora não cursada não passa para o período seguinte. A estratégia deixa de
ser "quanto apostar em cada uma" e passa a ser "quais pedir": um Problema da
Mochila 0-1, com a carga horária w_x como peso e a utilidade percebida u_{a,x}
como valor.

Os dois mecanismos resolvem, portanto, mochilas de naturezas diferentes. A daqui
é **0-1**: o item entra ou não, e a utilidade é cobrada uma vez só. A do leilão é
**côncava** e de pesos unitários (`behavior.compute_bids`): o aluno põe quantos
créditos quiser na mesma disciplina, com retorno decrescente. Essa é a
expressividade que a comparação mede — aqui a utilidade só ordena, lá ela também
dosa.

As duas peças deste módulo são justamente essas: `request_set` (o que o aluno
pede) e `allocate_by_ranking` (o que a universidade concede).
"""
from __future__ import annotations

from .behavior import NEUTRAL, Behavior, Signals, decision_scores
from .entities import Agent, Demand, Good, Problem
from .wdp_solver import solve_wdp

from math import gcd


def _knapsack(
    *, names: list[str], values: dict[str, float], weights: dict[str, int], capacity: int
) -> list[str]:
    """Mochila 0-1 exata: o subconjunto de `names` de maior valor somado que
    cabe em `capacity`.

    Resolvida por programação dinâmica, não por PLI: a instância é de um aluno
    só, com dezenas de itens e uma capacidade em horas, e a tabela é muito mais
    barata que uma chamada ao CBC — que aqui seria feita uma vez por aluno, por
    rodada, por período.

    Dois cortes mantêm a tabela pequena. Se tudo cabe, não há escolha a fazer.
    E, como os pesos são inteiros, dividir todos eles e a capacidade pelo MDC dá
    exatamente o mesmo ótimo numa tabela MDC vezes menor — uma grade de
    disciplinas de 60 e 90 h encolhe a capacidade de 450 para 15.

    **Empate de valor vai para quem vem antes em `names`**, que é a ordem de
    desempate global descrita em `behavior`. Sai de graça da comparação estrita
    em `candidate > best[c]`: um item posterior não desloca um valor igual já
    alcançado pelos anteriores, e a reconstrução de trás para frente respeita
    isso. Quem chama precisa, portanto, passar `names` na ordem da grade.
    """
    pool = [name for name in names if weights[name] <= capacity]
    if not pool:
        return []
    if sum(weights[name] for name in pool) <= capacity:
        return pool

    unit = 0
    for name in pool:
        unit = gcd(unit, weights[name])
    scaled = {name: weights[name] // unit for name in pool}
    room = capacity // unit

    # best[c] = maior valor com capacidade c usando os itens já percorridos;
    # taken[i][c] diz se o i-ésimo item entra na solução ótima daquele estado,
    # que é o que permite reconstruir o conjunto no fim.
    best = [0.0] * (room + 1)
    taken: list[list[bool]] = []
    for name in pool:
        weight, value = scaled[name], values[name]
        row = [False] * (room + 1)
        # De trás para frente seria a versão em vetor único; aqui a linha nova é
        # escrita à parte porque `taken` precisa do estado anterior intacto.
        updated = best[:]
        for c in range(weight, room + 1):
            candidate = best[c - weight] + value
            if candidate > best[c]:
                updated[c] = candidate
                row[c] = True
        best = updated
        taken.append(row)

    chosen: list[str] = []
    c = room
    for i in range(len(pool) - 1, -1, -1):
        if taken[i][c]:
            chosen.append(pool[i])
            c -= scaled[pool[i]]
    chosen.reverse()
    return chosen


def request_set(
    *,
    utilities: dict[str, float],
    available: list[str],
    behavior: Behavior = NEUTRAL,
    signals: Signals | None = None,
    catalogue: int = 0,
) -> list[str]:
    """D_a^(t,r) — as disciplinas que o aluno solicita nesta rodada, eq. (50),
    **na ordem de preferência dele**.

    `available` é B_a^(t,r), o mesmo conjunto que alimenta os lances no leilão:
    disciplinas com vaga livre que o aluno ainda não conquistou no período. Ele
    pede **todas**, da que mais quer para a que menos quer.

    **A mochila 0-1 saiu daqui.** Antes o aluno resolvia a carga horária em
    casa, escolhendo *ex-ante* o subconjunto que coubesse em W_a; agora ele
    apresenta a lista inteira e a restrição é resolvida na concessão. Três
    razões, e a primeira é a que motivou a mudança:

    1. **Sem isso o eixo ordenação × PLI não existe deste lado.** Com o pedido
       já cabendo em W_a por construção, a carga nunca apertava no alocador, o
       problema se separava por disciplina e os dois resolvedores davam sempre
       a mesma alocação.
    2. **É à prova de estratégia.** Pedido recusado não custa nada e a
       prioridade do aluno não depende do que ele pede, então listar tudo na
       ordem verdadeira é dominante — não há o que o aluno ganhe mentindo.
    3. **É o que a universidade real faz**: o aluno se inscreve numa lista
       ordenada maior do que cabe, e o sistema para quando a grade enche.

    Pedir tudo não quer dizer levar tudo: quem corta é o alocador, e o aluno
    perde o que menos queria (na ditadura serial) ou o que o ótimo global
    dispensar (na PLI).
    """
    wanted = set(available)
    scores = decision_scores(
        utilities=utilities,
        behavior=behavior,
        signals=signals,
        catalogue=catalogue,
    )
    # Ordenação **estável** sobre um dicionário que já vem na ordem da grade:
    # scores empatados saem na ordem de listagem do cenário, a mesma que
    # desempata o lance (ver `ORDEM DE DESEMPATE`, em `behavior`). Pôr o nome
    # na chave desempataria por alfabeto, que não é critério nenhum.
    #
    # A reserva corta aqui também: pedir o que se quer pouco custa carga, e com
    # r > 0 o aluno deixa de pedir abaixo do limiar.
    ordered = sorted(
        ((name, score) for name, score in scores.items() if name in wanted),
        key=lambda item: -item[1],
    )
    return [name for name, score in ordered if score > behavior.reserve]


def allocate_by_ranking(
    *,
    requests: list[tuple[str, str]],
    priority: dict[str, float],
    seats: dict[str, int],
    hours: dict[str, int],
    capacity: dict[str, int],
) -> list[tuple[str, str]]:
    """Ditadura serial: os alunos entram em ordem decrescente de CR e cada um
    leva o que quer, na própria ordem de preferência, enquanto houver vaga e
    carga — a distribuição da Seção 7.3.1.

    `requests` vem **já na ordem de preferência de cada aluno**, e `priority` é
    por **aluno** (N_a da eq. 49 mais a perturbação de desempate), não por par.
    Essa separação é o que torna a regra lexicográfica de verdade: o CR decide
    *quem* escolhe antes, e a utilidade decide *o que* cada um escolhe. Com uma
    ordenação achatada sobre os pares, o epsilon por par embaralharia a ordem
    interna do aluno e ele levaria o que calhasse, não o que preferia.

    **A carga horária é verificada aqui, não em casa.** O aluno pede tudo que
    lhe é elegível e a restrição da eq. (4) é resolvida *ex-post*, na concessão
    — que é o que torna comparável a célula gulosa com a de PLI: as duas
    recebem a mesma mensagem e só diferem em quem decide.

    `seats` e `capacity` não são modificados: a concessão é descontada em
    cópias, e quem chamou aplica o resultado ao próprio estado.
    """
    remaining = dict(seats)
    room = dict(capacity)
    by_student: dict[str, list[str]] = {}
    for student_id, name in requests:
        by_student.setdefault(student_id, []).append(name)

    granted: list[tuple[str, str]] = []
    for student_id in sorted(by_student, key=lambda s: (-priority[s], s)):
        for name in by_student[student_id]:
            if remaining.get(name, 0) > 0 and room.get(student_id, 0) >= hours[name]:
                remaining[name] -= 1
                room[student_id] -= hours[name]
                granted.append((student_id, name))
    return granted


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

    É a célula "CR × PLI" do 2x2, e ela usa **o mesmo resolvedor do leilão** —
    só muda o peso da preferência, que ali é o lance e aqui é o CR. Isso torna
    o eixo exato por construção: nada além do resolvedor difere entre as
    células de uma linha.

    **Um defeito a declarar**, e ele é do mecanismo, não da implementação: como
    todas as demandas de um aluno têm o mesmo peso `N_a`, a PLI é indiferente
    sobre *qual* dos pedidos dele cortar quando a carga aperta, e usa essa
    liberdade para liberar vaga aos outros. O aluno não tem voz sobre o que
    perde — ao contrário da ditadura serial, em que ele perde o que menos
    queria. É a diferença entre tratar o CR como fila e como peso.
    """
    if not requests:
        return []
    demands = [
        Demand(student_id, name, priority[student_id])
        for student_id, name in requests
    ]
    problem = Problem(
        agents=[Agent(student_id, capacity[student_id]) for student_id in capacity],
        goods=[Good(name, seats[name], hours[name]) for name in seats],
        demands=demands,
    )
    allocation = solve_wdp(problem)
    return [key for key, taken in allocation.items() if taken]
