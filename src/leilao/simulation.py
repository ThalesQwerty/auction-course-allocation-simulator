"""Orquestrador de comparação: roda os dois mecanismos sobre o mesmo cenário.

Implementa a metodologia de comparação controlada (Seção 7.3): mesmos
agentes, bens, utilidades e demandas são usados para o leilão por créditos e
para a linha de base por CR, isolando o nexo causal ao mecanismo interno.
"""
from __future__ import annotations

from dataclasses import dataclass

from .auction import AuctionResult, run_auction
from .cr_mechanism import CRResult, run_cr_allocation
from .metrics import MetricsReport, build_metrics_report
from .scenario import Scenario


@dataclass
class ComparisonResult:
    scenario_id: str
    auction: AuctionResult
    auction_metrics: MetricsReport
    cr: CRResult
    cr_metrics: MetricsReport


def run_comparison(scenario: Scenario) -> ComparisonResult:
    """Executa o leilão por créditos e a linha de base por CR sobre `scenario`."""
    utilities = scenario.utilities_by_pair()
    goods = scenario.goods_entities()
    academic_index = scenario.academic_index_by_agent()

    auction_result = run_auction(scenario.to_auction_config())
    auction_metrics = build_metrics_report(
        utilities=utilities,
        allocation=auction_result.final_allocation,
        goods=goods,
        academic_index=academic_index,
    )

    cr_result = run_cr_allocation(scenario.to_cr_config())
    cr_metrics = build_metrics_report(
        utilities=utilities,
        allocation=cr_result.allocation,
        goods=goods,
        academic_index=academic_index,
    )

    return ComparisonResult(
        scenario_id=scenario.id,
        auction=auction_result,
        auction_metrics=auction_metrics,
        cr=cr_result,
        cr_metrics=cr_metrics,
    )
