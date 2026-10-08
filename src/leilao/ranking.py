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
C_a^(t,r) entre lances proporcionais à utilidade; aqui ele gasta W_a^(t,r) em
horas, e U_a^(t) continua sendo a fração daquele teto que ele se dispõe a usar
(eq. 50). A estratégia deixa de ser "quanto apostar em cada uma" e passa a ser
"quais pedir": um Problema da Mochila 0-1, com a carga horária w_x como peso e
a utilidade percebida u_{a,x} como valor.

As duas peças deste módulo são justamente essas: `request_set` (o que o aluno
pede) e `allocate_by_ranking` (o que a universidade concede).
"""
from __future__ import annotations

import math
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
    hours: dict[str, int],
    capacity: int,
    spend_fraction: float,
) -> list[str]:
    """D_a^(t,r) — as disciplinas que o aluno solicita nesta rodada, eq. (50).

    `available` é B_a^(t,r), o mesmo conjunto que alimenta os lances no leilão:
    disciplinas com vaga livre, que cabem na carga horária restante e que o
    aluno ainda não conquistou no período. `capacity` é W_a^(t,r), a carga
    horária que lhe sobra, e `spend_fraction` é U_a^(t).

    O teto do pedido é floor(U_a * W_a) — a eq. (50) com os dois lados em horas
    inteiras. É o análogo exato do que o leilão faz com o orçamento na eq. (44):
    U_a é a fração do que o aluno tem em mãos que ele se dispõe a comprometer no
    período, e o que muda entre os mecanismos é só a moeda.

    Dentro desse teto o aluno extrai o máximo de utilidade que consegue, e é
    aqui que ele deixa de poder dizer *quanto* quer cada disciplina: a mochila
    só lê a ordem das utilidades e os pesos. Essa perda de expressividade é
    justamente a hipótese que a comparação testa.
    """
    pool = [name for name in available if utilities.get(name, 0.0) > 0.0]
    if not pool:
        return []
    return _knapsack(
        names=pool,
        values=utilities,
        weights=hours,
        capacity=math.floor(spend_fraction * capacity),
    )


def allocate_by_ranking(
    *,
    requests: list[tuple[str, str]],
    priority: dict[tuple[str, str], float],
    seats: dict[str, int],
) -> list[tuple[str, str]]:
    """Atende as solicitações em ordem decrescente de prioridade, enquanto
    houver vaga — a distribuição da Seção 7.3.1.

    `priority` é N_a^(t) + epsilon_{a,x}: o CR do aluno (eq. 49) mais a mesma
    matriz de perturbações estocásticas que o leilão usa. O epsilon está aqui
    pelo mesmo motivo de lá — dar a cada solicitação um valor único, de modo que
    a ordem não dependa de como a lista chegou. Sem ele dois alunos de CR igual
    disputando a última vaga seriam decididos pela ordem de iteração, que não é
    critério nenhum.

    Note que o CR é **do aluno**, não do par: um aluno de CR alto passa na
    frente em *todas* as disciplinas que pediu, e é essa concentração de
    vantagem que o leilão por créditos se propõe a dissolver, obrigando quem
    quer muito uma vaga a abrir mão de outra.

    `seats` não é modificado — a vaga concedida é descontada numa cópia, e quem
    chamou aplica o resultado ao próprio estado, como faz com a alocação do
    leilão.
    """
    remaining = dict(seats)
    granted: list[tuple[str, str]] = []
    # O desempate pelo próprio par é redundante enquanto epsilon for distinto
    # por par, e está aqui para que a ordenação siga total mesmo se alguém
    # passar prioridades repetidas.
    for key in sorted(requests, key=lambda k: (-priority[k], k)):
        if remaining.get(key[1], 0) > 0:
            remaining[key[1]] -= 1
            granted.append(key)
    return granted
