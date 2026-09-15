from leilao.scenario import Scenario, ScenarioAgent, ScenarioDemand, ScenarioGood
from leilao.simulation import run_comparison


def _sample_scenario() -> Scenario:
    return Scenario(
        id="s1",
        name="cenário de teste",
        agents=[
            ScenarioAgent("a1", capacity=10, budget=100, academic_index=9.0),
            ScenarioAgent("a2", capacity=10, budget=100, academic_index=4.0),
        ],
        goods=[ScenarioGood("x1", quantity=1, weight=4)],
        demands=[
            ScenarioDemand("a1", "x1", utility=1.0),
            ScenarioDemand("a2", "x1", utility=1.0),
        ],
        num_rounds=1,
        seed=123,
    )


def test_run_comparison_produces_both_mechanisms():
    scenario = _sample_scenario()
    result = run_comparison(scenario)

    assert result.scenario_id == "s1"
    assert result.auction_metrics.average_satisfaction >= 0
    assert result.cr_metrics.average_satisfaction >= 0
    # Ambos os mecanismos só têm 1 vaga para 2 candidatos -> ocupação total = 1.
    assert result.auction_metrics.occupation_rate == 1.0
    assert result.cr_metrics.occupation_rate == 1.0


def test_cr_baseline_always_favors_higher_academic_index_here():
    # Com utilidades empatadas, o CR deve alocar para a1 (índice 9.0 > 4.0).
    scenario = _sample_scenario()
    result = run_comparison(scenario)
    assert result.cr.allocation[("a1", "x1")] == 1
    assert result.cr.allocation.get(("a2", "x1"), 0) == 0


def test_scenario_json_roundtrip(tmp_path):
    scenario = _sample_scenario()
    path = tmp_path / "scenario.json"
    scenario.save(path)
    loaded = Scenario.load(path)
    assert loaded.to_dict() == scenario.to_dict()

    # E o cenário recarregado deve produzir exatamente os mesmos resultados
    # (determinismo dado o mesmo seed — requisito metodológico da Seção 7.3).
    result_original = run_comparison(scenario)
    result_loaded = run_comparison(loaded)
    assert result_original.auction.final_allocation == result_loaded.auction.final_allocation
    assert result_original.cr.allocation == result_loaded.cr.allocation
