from leilao.cr_mechanism import CRAgent, CRConfig, CRDemandCandidate, CRGood, run_cr_allocation
from leilao.entities import MutualExclusion


def test_higher_academic_index_wins_scarce_good():
    config = CRConfig(
        agents=[CRAgent("a1", capacity=10, academic_index=9.0), CRAgent("a2", capacity=10, academic_index=6.0)],
        goods=[CRGood("x1", quantity=1, weight=1)],
        demands=[
            CRDemandCandidate("a1", "x1", utility=1.0),
            CRDemandCandidate("a2", "x1", utility=1.0),
        ],
        seed=1,
    )
    result = run_cr_allocation(config)
    assert result.allocation[("a1", "x1")] == 1
    assert result.allocation.get(("a2", "x1"), 0) == 0


def test_local_knapsack_respects_capacity_fraction():
    # Utilidade total = 1.0 (0.6 + 0.4), então U_a = 1.0 -> capacidade plena
    # disponível; mas peso de ambos (6+6=12) excede a capacidade (10), então
    # a mochila local escolhe apenas o de maior utilidade.
    config = CRConfig(
        agents=[CRAgent("a1", capacity=10, academic_index=8.0)],
        goods=[CRGood("x1", 1, weight=6), CRGood("x2", 1, weight=6)],
        demands=[
            CRDemandCandidate("a1", "x1", utility=0.6),
            CRDemandCandidate("a1", "x2", utility=0.4),
        ],
        seed=1,
    )
    result = run_cr_allocation(config)
    assert result.requested[("a1", "x1")] == 1
    assert result.requested.get(("a1", "x2"), 0) == 0


def test_mutual_exclusion_respected_locally():
    config = CRConfig(
        agents=[CRAgent("a1", capacity=100, academic_index=8.0)],
        goods=[CRGood("x1", 1, 1), CRGood("x2", 1, 1)],
        demands=[
            CRDemandCandidate("a1", "x1", 0.5),
            CRDemandCandidate("a1", "x2", 0.5),
        ],
        exclusions=[MutualExclusion(frozenset({"x1", "x2"}))],
        seed=1,
    )
    result = run_cr_allocation(config)
    assert sum(result.requested.values()) == 1


def test_scarcity_rejects_lower_priority_request():
    config = CRConfig(
        agents=[CRAgent("a1", 10, academic_index=9.0), CRAgent("a2", 10, academic_index=5.0)],
        goods=[CRGood("x1", quantity=1, weight=1)],
        demands=[
            CRDemandCandidate("a1", "x1", 1.0),
            CRDemandCandidate("a2", "x1", 1.0),
        ],
        seed=1,
    )
    result = run_cr_allocation(config)
    assert result.allocation[("a1", "x1")] == 1
    assert result.allocation[("a2", "x1")] == 0
    assert result.requested[("a2", "x1")] == 1  # solicitou, mas não foi atendido


def test_empty_demands_returns_empty_result():
    config = CRConfig(agents=[CRAgent("a1", 10, 8.0)], goods=[CRGood("x1", 1, 1)], demands=[])
    result = run_cr_allocation(config)
    assert result.requested == {}
    assert result.allocation == {}
