"""Resolvedor do Problema de Determinação de Vencedores (WDP).

`solve_wdp` é a função resolvedora O(P) = z_max da eq. (10), exata, por PLI.

Houve um segundo resolvedor aqui até 24/11/2026 — `solve_wdp_greedy`, a
varredura por preferência decrescente —, com a mesma assinatura, para que
"quem decide a alocação" pudesse ser um eixo da comparação. Saiu com o
fechamento do escopo: o leilão é o da PLI, e a varredura era degrau de
ablação. Quem ainda varre por preferência é a linha de base por CR, mas por
`equations.serial_dictatorship`, que é outra regra.

O PLI maximiza a preferência agregada dos bens alocados:

    max  Z = Σ_{(a,x) ∈ D} p_{a,x} · z_{a,x}                        (eq. 8)

sujeito a

    Σ_{a ∈ A} z_{a,x} ≤ q_x              ∀ x ∈ B                    (eq. 3)
    Σ_{x ∈ B} z_{a,x} · w_x ≤ W_a        ∀ a ∈ A                    (eq. 4)
    Σ_{x ∈ Y} z_{a,x} ≤ 1                ∀ a ∈ A, ∀ Y ∈ X           (eq. 5)
    z_{a,x} ∈ {0, 1}                     ∀ (a,x) ∈ D                (eq. 1)

É uma extensão do 0-1 Multiple Knapsack Problem with Shared Items and
Conflict Graphs, NP-difícil (Seções 3.1 e 6.2).

O objetivo não tem forma pura em `equations/` porque ele é montado
simbolicamente, como expressão do PuLP — não há valor a calcular aqui.

Por que o desempate não entra no PLI
------------------------------------

O ε decide empates na varredura gulosa e na ditadura serial, onde é só uma
chave de ordenação e não custa nada. No PLI ele não entra — nem somado ao
objetivo, nem como segundo estágio sobre o conjunto dos ótimos. As duas
saídas foram tentadas, e as duas falham por motivos diferentes.

**Somar as camadas num objetivo só** esbarra na tolerância numérica. Para o
desempate nunca inverter uma unidade da grandeza principal, a soma dele sobre
os pares alocados tem de ficar abaixo de 1 — cada termo abaixo de 1/(total de
vagas), o que no cenário cheio dá 9·10⁻⁵. Só que metade das demandas são
lances de 1 crédito: são ~35 mil pares exatamente empatados, e separá-los
exigiria passos de 2,5·10⁻⁹, uns 400× abaixo da tolerância de 10⁻⁶ do CBC.
Não é questão de calibrar a escala — entre o teto e a tolerância cabem ~90
níveis distintos, e seriam precisos 35 mil. Foi isso que derrubou a eq. (22)
do anteprojeto, que somava e por isso chegou a trocar quinze créditos de
lance por prioridade agregada.

**Resolver em dois estágios** — fixar Σ p·z ≥ M e maximizar só o ε sobre a
face ótima — escapa da tolerância, porque ali a escala do desempate é livre.
Mas troca um problema numérico por um combinatório pior: a restrição prende a
região viável à face ótima, onde todo nó do branch-and-bound tem praticamente
o mesmo limitante e nada poda — o solver enumera a face inteira. Medido: uma
instância de **1.168 variáveis** ficou 5h38 sem fechar. E o estágio 2 fica
mais caro exatamente quando há mais empate, que é quando ele serviria.

**O que isso custa:** o ótimo do PLI não é único, e qual deles o CBC devolve
depende da busca dele. O *valor* do objetivo é único — é ele que a comparação
mede —, e a alocação é reprodutível para um mesmo binário do CBC; entre
plataformas diferentes não há garantia.
"""
from __future__ import annotations

import pulp

from .entities import Allocation, Demand, Problem

# Quando toda preferência é inteira — o caso do leilão, em que ela é o lance
# em créditos —, o objetivo só pode melhorar de 1 em 1. Dizer isso ao CBC o
# autoriza a podar todo nó cujo limitante não supere o incumbente por uma
# unidade inteira, e a poda é exata: não existe solução entre o incumbente e o
# próximo valor possível. Fica em 0,99, e não em 1, para que o acúmulo de
# ponto flutuante não leia uma melhora real de 1 como 0,999... e a descarte.
INTEGER_INCREMENT = 0.99


class InfeasibleOrUnsolvedError(RuntimeError):
    """Levantado quando o solver não encontra solução ótima comprovada."""


def _model(problem: Problem) -> tuple[pulp.LpProblem, dict[tuple[str, str], pulp.LpVariable]]:
    """As restrições (3), (4) e (5) — as mesmas em qualquer objetivo."""
    lp = pulp.LpProblem("WDP", pulp.LpMaximize)

    # Variáveis nomeadas por índice, e não pelos ids: ids de domínio podem
    # conter espaços e acentos ("Cálculo I"), que não sobrevivem ao formato LP
    # lido pelo CBC.
    variables = {
        (d.agent_id, d.good_id): pulp.LpVariable(f"z_{i}", cat="Binary")
        for i, d in enumerate(problem.demands)
    }

    by_good: dict[str, list[pulp.LpVariable]] = {}
    by_agent: dict[str, list[tuple[str, pulp.LpVariable]]] = {}
    for demand in problem.demands:
        variable = variables[(demand.agent_id, demand.good_id)]
        by_good.setdefault(demand.good_id, []).append(variable)
        by_agent.setdefault(demand.agent_id, []).append((demand.good_id, variable))

    for i, good in enumerate(problem.goods):
        if by_good.get(good.id):
            lp += pulp.lpSum(by_good[good.id]) <= good.quantity, f"quantity_{i}"

    weight = {g.id: g.weight for g in problem.goods}
    for i, agent in enumerate(problem.agents):
        terms = [weight[gid] * var for gid, var in by_agent.get(agent.id, [])]
        if terms:
            lp += pulp.lpSum(terms) <= agent.capacity, f"capacity_{i}"

    for i, agent in enumerate(problem.agents):
        for j, exclusion in enumerate(problem.exclusions):
            clique = [
                variables[(agent.id, good_id)]
                for good_id in exclusion.goods
                if (agent.id, good_id) in variables
            ]
            if len(clique) > 1:
                lp += pulp.lpSum(clique) <= 1, f"exclusion_{i}_{j}"

    return lp, variables


def _increment(problem: Problem) -> float | None:
    """O passo mínimo do objetivo, quando dá para afirmar um — ver `INTEGER_INCREMENT`."""
    if all(float(d.preference).is_integer() for d in problem.demands):
        return INTEGER_INCREMENT
    return None


def _solve(lp: pulp.LpProblem, *, msg: bool, increment: float | None) -> None:
    # O PuLP prefixa com "-" cada item de `options`, então a opção e o valor
    # vão numa string só; em itens separados isso viraria "--increment -0.99".
    options = [] if increment is None else [f"increment {increment}"]
    status = pulp.LpStatus[lp.solve(pulp.PULP_CBC_CMD(msg=msg, options=options))]
    if status != "Optimal":
        raise InfeasibleOrUnsolvedError(f"WDP solver returned status {status!r}")


def _taken(
    variables: dict[tuple[str, str], pulp.LpVariable]
) -> dict[tuple[str, str], int]:
    return {key: int(round(var.value())) for key, var in variables.items()}


def solve_wdp(problem: Problem, *, msg: bool = False) -> Allocation:
    """z_max por PLI — eq. (10).

    Retorna apenas as entradas (a, x) ∈ D; pares fora de D são 0 por
    definição (eq. 2) e não aparecem no dicionário.

    **`Demand.tiebreak` é ignorado aqui** — ver o docstring do módulo. Quem o
    usa é a varredura gulosa, logo abaixo, e a ditadura serial.
    """
    if not problem.demands:
        return {}

    lp, variables = _model(problem)
    lp.setObjective(
        pulp.lpSum(
            d.preference * variables[(d.agent_id, d.good_id)] for d in problem.demands
        )
    )
    _solve(lp, msg=msg, increment=_increment(problem))
    return _taken(variables)


