import pytest

from leilao.auction import AuctionInput, Bid, run_auction
from leilao.entities import Agent, Good, MutualExclusion


def test_higher_bidder_wins_single_good():
    auction_input = AuctionInput(
        agents=[Agent("a1", capacity=10), Agent("a2", capacity=10)],
        goods=[Good("x1", quantity=1, weight=1)],
        budgets={"a1": 100, "a2": 100},
        bids=[Bid("a1", "x1", 80), Bid("a2", "x1", 20)],
        seed=42,
    )
    result = run_auction(auction_input)
    assert result.allocation[("a1", "x1")] == 1
    assert result.allocation.get(("a2", "x1"), 0) == 0


def test_price_is_second_highest_unsuccessful_bid():
    auction_input = AuctionInput(
        agents=[Agent("a1", 10), Agent("a2", 10), Agent("a3", 10)],
        goods=[Good("x1", quantity=1, weight=1)],
        budgets={"a1": 100, "a2": 100, "a3": 100},
        bids=[Bid("a1", "x1", 90), Bid("a2", "x1", 50), Bid("a3", "x1", 10)],
        seed=1,
    )
    result = run_auction(auction_input)
    assert result.allocation[("a1", "x1")] == 1
    # eq. (24): preço = maior lance mal-sucedido (o de a2, 50 créditos)
    assert result.prices["x1"] == 50
    # eq. (25): consumo do vencedor é o preço de mercado, não o próprio lance
    assert result.consumption[("a1", "x1")] == 50
    assert result.remaining_budget["a1"] == 50


def test_price_defaults_to_one_when_no_unsuccessful_bids():
    auction_input = AuctionInput(
        agents=[Agent("a1", 10)],
        goods=[Good("x1", quantity=1, weight=1)],
        budgets={"a1": 100},
        bids=[Bid("a1", "x1", 30)],
        seed=1,
    )
    result = run_auction(auction_input)
    assert result.prices["x1"] == 1.0
    assert result.consumption[("a1", "x1")] == 1.0


def test_capacity_constraint_prevents_overload():
    auction_input = AuctionInput(
        agents=[Agent("a1", capacity=6)],
        goods=[Good("x1", 1, weight=6), Good("x2", 1, weight=6)],
        budgets={"a1": 100},
        bids=[Bid("a1", "x1", 40), Bid("a1", "x2", 60)],
        seed=1,
    )
    result = run_auction(auction_input)
    # capacidade só comporta um dos dois bens -> vence o de maior lance (x2)
    assert result.allocation[("a1", "x2")] == 1
    assert result.allocation[("a1", "x1")] == 0


def test_mutual_exclusion_prevents_both_goods_winning():
    auction_input = AuctionInput(
        agents=[Agent("a1", capacity=100)],
        goods=[Good("x1", 1, 1), Good("x2", 1, 1)],
        budgets={"a1": 100},
        bids=[Bid("a1", "x1", 30), Bid("a1", "x2", 30)],
        exclusions=[MutualExclusion(frozenset({"x1", "x2"}))],
        seed=1,
    )
    result = run_auction(auction_input)
    assert sum(result.allocation.values()) == 1


def test_budget_overspend_raises_before_solving():
    with pytest.raises(ValueError, match="excedem o orçamento"):
        AuctionInput(
            agents=[Agent("a1", capacity=10)],
            goods=[Good("x1", 1, 1), Good("x2", 1, 1)],
            budgets={"a1": 10},
            bids=[Bid("a1", "x1", 6), Bid("a1", "x2", 6)],
        )


def test_missing_budget_raises():
    with pytest.raises(ValueError, match="sem orçamento"):
        AuctionInput(
            agents=[Agent("a1", capacity=10)],
            goods=[Good("x1", 1, 1)],
            budgets={},
            bids=[Bid("a1", "x1", 5)],
        )


def test_no_bids_returns_empty_result():
    auction_input = AuctionInput(
        agents=[Agent("a1", 10)],
        goods=[Good("x1", 1, 1)],
        budgets={"a1": 100},
        bids=[],
    )
    result = run_auction(auction_input)
    assert result.allocation == {}
    assert result.remaining_budget == {"a1": 100}


def test_deterministic_given_same_seed():
    def build() -> AuctionInput:
        return AuctionInput(
            agents=[Agent("a1", 10), Agent("a2", 10)],
            goods=[Good("x1", 1, 1)],
            budgets={"a1": 50, "a2": 50},
            bids=[Bid("a1", "x1", 25), Bid("a2", "x1", 25)],
            seed=99,
        )

    result_a = run_auction(build())
    result_b = run_auction(build())
    assert result_a.allocation == result_b.allocation
    assert result_a.prices == result_b.prices
