import random

import pytest

from leilao.entities import Agent, Demand, Good, MutualExclusion, Problem
from leilao.wdp_solver import AllocationTimeout, solve_wdp


def test_single_agent_single_good_within_capacity():
    problem = Problem(
        agents=[Agent("a1", capacity=10)],
        goods=[Good("x1", quantity=1, weight=4)],
        demands=[Demand("a1", "x1", preference=5)],
    )
    allocation = solve_wdp(problem)
    assert allocation[("a1", "x1")] == 1


def test_quantity_constraint_limits_allocation():
    problem = Problem(
        agents=[Agent("a1", 10), Agent("a2", 10), Agent("a3", 10)],
        goods=[Good("x1", quantity=1, weight=1)],
        demands=[
            Demand("a1", "x1", preference=3),
            Demand("a2", "x1", preference=5),
            Demand("a3", "x1", preference=1),
        ],
    )
    allocation = solve_wdp(problem)
    assert allocation[("a2", "x1")] == 1
    assert allocation[("a1", "x1")] == 0
    assert allocation[("a3", "x1")] == 0


def test_capacity_constraint_prevents_overload():
    problem = Problem(
        agents=[Agent("a1", capacity=10)],
        goods=[Good("x1", 1, weight=6), Good("x2", 1, weight=6)],
        demands=[
            Demand("a1", "x1", preference=5),
            Demand("a1", "x2", preference=8),
        ],
    )
    allocation = solve_wdp(problem)
    assert allocation[("a1", "x2")] == 1
    assert allocation[("a1", "x1")] == 0


def test_mutual_exclusion_clique_limits_to_one():
    problem = Problem(
        agents=[Agent("a1", capacity=100)],
        goods=[Good("x1", 1, 1), Good("x2", 1, 1)],
        demands=[
            Demand("a1", "x1", preference=5),
            Demand("a1", "x2", preference=9),
        ],
        exclusions=[MutualExclusion(frozenset({"x1", "x2"}))],
    )
    allocation = solve_wdp(problem)
    assert sum(allocation.values()) == 1
    assert allocation[("a1", "x2")] == 1


def test_maximizes_aggregate_preference_not_count():
    problem = Problem(
        agents=[Agent("a1", capacity=5)],
        goods=[Good("x1", 1, 5), Good("x2", 1, 2), Good("x3", 1, 2)],
        demands=[
            Demand("a1", "x1", preference=10),
            Demand("a1", "x2", preference=3),
            Demand("a1", "x3", preference=3),
        ],
    )
    allocation = solve_wdp(problem)
    assert allocation[("a1", "x1")] == 1
    assert allocation[("a1", "x2")] == 0
    assert allocation[("a1", "x3")] == 0


def test_empty_demands_returns_empty_allocation():
    problem = Problem(agents=[Agent("a1", 10)], goods=[Good("x1", 1, 1)], demands=[])
    assert solve_wdp(problem) == {}


def test_the_ilp_ignores_the_tiebreak_but_still_returns_an_optimum():
    """A PLI não desempata — o que ela garante é o valor, não qual empatado."""
    problem = Problem(
        agents=[Agent("a1", 10), Agent("a2", 10), Agent("a3", 10)],
        goods=[Good("x1", quantity=2, weight=1)],
        demands=[
            Demand("a1", "x1", preference=5, tiebreak=0.1),
            Demand("a2", "x1", preference=5, tiebreak=0.7),
            Demand("a3", "x1", preference=5, tiebreak=0.4),
        ],
    )
    allocation = solve_wdp(problem)
    assert sum(allocation.values()) == 2
    granted = sum(
        demand.preference
        for demand in problem.demands
        if allocation[(demand.agent_id, demand.good_id)]
    )
    assert granted == 10


def test_the_tiebreak_never_buys_preference():
    """O caso que derrubou a eq. (22): somar as camadas dá a resposta errada."""
    problem = Problem(
        agents=[Agent("a1", capacity=2), Agent("a2", capacity=1)],
        goods=[Good("x1", 1, 1), Good("x2", 1, 1), Good("x3", 1, 1)],
        demands=[
            Demand("a1", "x1", preference=5, tiebreak=0.0),
            Demand("a1", "x2", preference=1, tiebreak=0.0),
            Demand("a1", "x3", preference=0.5, tiebreak=0.0),
            Demand("a2", "x1", preference=4, tiebreak=0.9),
        ],
    )
    allocation = solve_wdp(problem)
    granted = sum(
        demand.preference
        for demand in problem.demands
        if allocation[(demand.agent_id, demand.good_id)]
    )
    assert granted == 6.0
    assert allocation[("a1", "x1")] == 1
    assert allocation[("a2", "x1")] == 0


def _knapsack(agents=40, goods=24) -> Problem:
    """Uma instância em que provar o ótimo custa: preferência e peso quase
    proporcionais, que é o que deixa o limite linear longe do inteiro."""
    rng = random.Random(7)
    pesos = {f"x{j}": rng.randint(40, 70) for j in range(goods)}
    return Problem(
        agents=[Agent(f"a{i}", capacity=180) for i in range(agents)],
        goods=[Good(name, quantity=3, weight=peso) for name, peso in pesos.items()],
        demands=[
            Demand(f"a{i}", name, preference=peso + rng.random())
            for i in range(agents)
            for name, peso in pesos.items()
        ],
    )


def test_a_tight_time_limit_raises_instead_of_taking_the_feasible_solution():
    """Com `timeLimit` o pulp ainda devolve `Optimal` e a melhor solução que
    achou. Aproveitá-la daria alocação subótima sem ninguém notar."""
    with pytest.raises(AllocationTimeout):
        solve_wdp(_knapsack(), time_limit=0.01)


def test_a_generous_time_limit_does_not_change_the_allocation():
    """O teto muda quando o CBC para, não como ele busca: a simulação que não
    estoura sai idêntica à de um cenário sem teto."""
    problem = Problem(
        agents=[Agent("a1", 10), Agent("a2", 10)],
        goods=[Good("x1", 1, 4), Good("x2", 1, 4)],
        demands=[
            Demand("a1", "x1", preference=5),
            Demand("a1", "x2", preference=3),
            Demand("a2", "x1", preference=7),
            Demand("a2", "x2", preference=2),
        ],
    )
    assert solve_wdp(problem, time_limit=600) == solve_wdp(problem)
