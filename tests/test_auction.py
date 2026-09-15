from leilao.auction import AuctionAgent, AuctionConfig, AuctionDemand, AuctionGood, run_auction
from leilao.entities import MutualExclusion


def test_higher_bidder_wins_single_good():
    config = AuctionConfig(
        agents=[AuctionAgent("a1", capacity=10, budget=100), AuctionAgent("a2", capacity=10, budget=100)],
        goods=[AuctionGood("x1", quantity=1, weight=1)],
        demands=[
            AuctionDemand("a1", "x1", utility=1.0),
            AuctionDemand("a2", "x1", utility=0.2),
        ],
        num_rounds=1,
        seed=42,
    )
    result = run_auction(config)
    # a1 concentra toda utilidade em x1 (u=1.0) enquanto a2 só destina 0.2 do
    # orçamento a esse bem -> a1 dá um lance maior e vence.
    assert result.final_allocation[("a1", "x1")] == 1
    assert result.final_allocation.get(("a2", "x1"), 0) == 0


def test_price_is_second_highest_unsuccessful_bid():
    config = AuctionConfig(
        agents=[AuctionAgent("a1", 10, 100), AuctionAgent("a2", 10, 100), AuctionAgent("a3", 10, 100)],
        goods=[AuctionGood("x1", quantity=1, weight=1)],
        demands=[
            AuctionDemand("a1", "x1", 1.0),
            AuctionDemand("a2", "x1", 0.5),
            AuctionDemand("a3", "x1", 0.1),
        ],
        num_rounds=1,
        seed=1,
    )
    result = run_auction(config)
    round0 = result.rounds[0]
    winner = next(a for (a, x) in round0.allocation if round0.allocation[(a, x)] == 1)
    assert winner == "a1"
    # preço deve ser o maior lance mal-sucedido: o de a2 (50 creditos)
    assert round0.prices["x1"] == round0.bids[("a2", "x1")]
    # consumo do vencedor é o preço de mercado, não o próprio lance (2o preço)
    assert result.final_consumption[("a1", "x1")] == round0.prices["x1"]


def test_budget_constraint_respected_across_bids():
    config = AuctionConfig(
        agents=[AuctionAgent("a1", capacity=10, budget=10)],
        goods=[AuctionGood("x1", 1, 1), AuctionGood("x2", 1, 1)],
        demands=[
            AuctionDemand("a1", "x1", 0.5),
            AuctionDemand("a1", "x2", 0.5),
        ],
        num_rounds=1,
        seed=7,
    )
    result = run_auction(config)
    round0 = result.rounds[0]
    total_bid = sum(round0.bids.values())
    # eq. (19): soma dos lances não pode ultrapassar o orçamento do agente
    assert total_bid <= 10


def test_mutual_exclusion_prevents_both_goods_winning():
    config = AuctionConfig(
        agents=[AuctionAgent("a1", capacity=100, budget=20)],
        goods=[AuctionGood("x1", 1, 1), AuctionGood("x2", 1, 1)],
        demands=[
            AuctionDemand("a1", "x1", 0.5),
            AuctionDemand("a1", "x2", 0.5),
        ],
        exclusions=[MutualExclusion(frozenset({"x1", "x2"}))],
        num_rounds=1,
        seed=3,
    )
    result = run_auction(config)
    total_won = sum(result.final_allocation.values())
    assert total_won <= 1


def test_multi_round_frees_up_capacity_for_losers():
    # Rodada 1: a1 vence x1 (orçamento maior). Rodada 2: x1 já não existe mais
    # para a1 (eq. 15) e a2 ainda compete pelos bens remanescentes.
    config = AuctionConfig(
        agents=[AuctionAgent("a1", 10, 100), AuctionAgent("a2", 10, 100)],
        goods=[AuctionGood("x1", quantity=1, weight=1)],
        demands=[
            AuctionDemand("a1", "x1", 1.0),
            AuctionDemand("a2", "x1", 0.9),
        ],
        num_rounds=2,
        seed=5,
    )
    result = run_auction(config)
    assert result.final_allocation[("a1", "x1")] == 1
    # a2 nunca pode vencer x1 pois a quantidade já foi esgotada na rodada 1
    assert result.final_allocation.get(("a2", "x1"), 0) == 0
    assert len(result.rounds) <= 2


def test_deterministic_given_same_seed():
    def build():
        return AuctionConfig(
            agents=[AuctionAgent("a1", 10, 50), AuctionAgent("a2", 10, 50)],
            goods=[AuctionGood("x1", 1, 1)],
            demands=[AuctionDemand("a1", "x1", 0.5), AuctionDemand("a2", "x1", 0.5)],
            num_rounds=1,
            seed=99,
        )

    result_a = run_auction(build())
    result_b = run_auction(build())
    assert result_a.final_allocation == result_b.final_allocation
