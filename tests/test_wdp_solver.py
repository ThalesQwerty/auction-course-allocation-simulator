from leilao.entities import Agent, Demand, Good, MutualExclusion, Problem
from leilao.wdp_solver import solve_wdp, solve_wdp_greedy


def test_single_agent_single_good_within_capacity():
    problem = Problem(
        agents=[Agent("a1", capacity=10)],
        goods=[Good("x1", quantity=1, weight=4)],
        demands=[Demand("a1", "x1", preference=5)],
    )
    allocation = solve_wdp(problem)
    assert allocation[("a1", "x1")] == 1


def test_quantity_constraint_limits_allocation():
    # 3 agentes disputam 1 vaga (q_x = 1) — apenas o de maior preferência ganha.
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
    # Capacidade do agente comporta só um dos dois bens (peso 6 cada, capacidade 10).
    problem = Problem(
        agents=[Agent("a1", capacity=10)],
        goods=[Good("x1", 1, weight=6), Good("x2", 1, weight=6)],
        demands=[
            Demand("a1", "x1", preference=5),
            Demand("a1", "x2", preference=8),
        ],
    )
    allocation = solve_wdp(problem)
    # Maior preferência (x2) deve ser escolhida quando não cabem os dois.
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
    # Um bem de alto valor e peso pequeno é preferível a dois de baixo valor
    # quando a capacidade só permite escolher um conjunto.
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


# --- as duas camadas: grandeza do mecanismo, depois desempate --------------


def test_the_tiebreak_decides_only_among_equals():
    # Uma turma de 2 vagas, três candidatos com o mesmo lance: quem leva são
    # os dois de maior desempate. Quem garante isso é a varredura gulosa — a
    # PLI ignora o desempate, ver o docstring de `wdp_solver`.
    problem = Problem(
        agents=[Agent("a1", 10), Agent("a2", 10), Agent("a3", 10)],
        goods=[Good("x1", quantity=2, weight=1)],
        demands=[
            Demand("a1", "x1", preference=5, tiebreak=0.1),
            Demand("a2", "x1", preference=5, tiebreak=0.7),
            Demand("a3", "x1", preference=5, tiebreak=0.4),
        ],
    )
    allocation = solve_wdp_greedy(problem)
    assert allocation[("a2", "x1")] == 1
    assert allocation[("a3", "x1")] == 1
    assert allocation[("a1", "x1")] == 0


def test_the_ilp_ignores_the_tiebreak_but_still_returns_an_optimum():
    """A PLI não desempata — o que ela garante é o valor, não qual empatado.

    Prender a camada de lance por restrição para maximizar o ε em seguida
    deixa a busca presa à face ótima, sem o que podar: uma instância de 1.168
    variáveis binárias ficou 5h38 sem fechar. O que sobrevive é esta garantia.
    """
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
    """O caso que derrubou a eq. (22): somar as camadas dá a resposta errada.

    Somadas, a alocação {a1→x2, a1→x3, a2→x1} vale 6,4 contra 6,0 da
    {a1→x1, a1→x2} — e o solver escolheria a primeira, que entrega **menos**
    preferência (5,5 contra 6,0) em troca de desempate. Guarda contra alguém
    voltar a somar as camadas no objetivo da PLI.
    """
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
