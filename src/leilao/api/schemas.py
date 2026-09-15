"""Schemas Pydantic para a API — espelham as dataclasses de leilao.scenario
e leilao.simulation, servindo de contrato de validação e de documentação
OpenAPI automática para o front-end.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..auction import AuctionResult
from ..cr_mechanism import CRResult
from ..metrics import MetricsReport
from ..scenario import Scenario, ScenarioAgent, ScenarioDemand, ScenarioGood


class ScenarioAgentIn(BaseModel):
    id: str
    capacity: float = Field(gt=0, description="W_a — carga horária máxima do estudante")
    budget: int = Field(ge=0, description="C_a^(1) — orçamento inicial de créditos")
    academic_index: float = Field(ge=0, description="N_a — Coeficiente de Rendimento")


class ScenarioGoodIn(BaseModel):
    id: str
    quantity: int = Field(ge=0, description="q_x — vagas na disciplina")
    weight: float = Field(gt=0, description="w_x — carga horária da disciplina")


class ScenarioDemandIn(BaseModel):
    agent_id: str
    good_id: str
    utility: float = Field(gt=0, le=1, description="u_{a,x} — utilidade percebida")


class ScenarioIn(BaseModel):
    """Corpo de requisição para criar/atualizar um cenário."""

    name: str
    agents: list[ScenarioAgentIn] = Field(default_factory=list)
    goods: list[ScenarioGoodIn] = Field(default_factory=list)
    demands: list[ScenarioDemandIn] = Field(default_factory=list)
    exclusions: list[list[str]] = Field(default_factory=list, description="cliques de choque de horário")
    tie_break_order: dict[str, list[str]] = Field(default_factory=dict)
    bias: dict[str, int] = Field(default_factory=dict, description='chave "agent_id|good_id" -> beta bruto')
    num_rounds: int = Field(default=1, ge=1)
    seed: int = 0

    def to_scenario(self, scenario_id: str) -> Scenario:
        return Scenario(
            id=scenario_id,
            name=self.name,
            agents=[ScenarioAgent(**a.model_dump()) for a in self.agents],
            goods=[ScenarioGood(**g.model_dump()) for g in self.goods],
            demands=[ScenarioDemand(**d.model_dump()) for d in self.demands],
            exclusions=[list(c) for c in self.exclusions],
            tie_break_order=dict(self.tie_break_order),
            bias=dict(self.bias),
            num_rounds=self.num_rounds,
            seed=self.seed,
        )


class ScenarioOut(ScenarioIn):
    id: str

    @staticmethod
    def from_scenario(scenario: Scenario) -> "ScenarioOut":
        return ScenarioOut(id=scenario.id, **{k: v for k, v in scenario.to_dict().items() if k != "id"})


class MetricsOut(BaseModel):
    average_satisfaction: float
    occupation_rate: float
    fairness_index: float
    academic_correlation: float
    satisfaction_by_agent: dict[str, float]

    @staticmethod
    def from_report(report: MetricsReport) -> "MetricsOut":
        return MetricsOut(
            average_satisfaction=report.average_satisfaction,
            occupation_rate=report.occupation_rate,
            fairness_index=report.fairness_index,
            academic_correlation=report.academic_correlation,
            satisfaction_by_agent=report.satisfaction_by_agent,
        )


def _pair_dict_to_str(d: dict[tuple[str, str], float]) -> dict[str, float]:
    return {f"{a}|{x}": v for (a, x), v in d.items()}


class AuctionRoundOut(BaseModel):
    round_index: int
    bids: dict[str, int]
    allocation: dict[str, int]
    prices: dict[str, float]
    consumption: dict[str, float]


class AuctionResultOut(BaseModel):
    rounds: list[AuctionRoundOut]
    final_allocation: dict[str, int]
    final_consumption: dict[str, float]
    remaining_budget: dict[str, float]

    @staticmethod
    def from_result(result: AuctionResult) -> "AuctionResultOut":
        return AuctionResultOut(
            rounds=[
                AuctionRoundOut(
                    round_index=r.round_index,
                    bids=_pair_dict_to_str(r.bids),
                    allocation=_pair_dict_to_str(r.allocation),
                    prices=r.prices,
                    consumption=_pair_dict_to_str(r.consumption),
                )
                for r in result.rounds
            ],
            final_allocation=_pair_dict_to_str(result.final_allocation),
            final_consumption=_pair_dict_to_str(result.final_consumption),
            remaining_budget=result.remaining_budget,
        )


class CRResultOut(BaseModel):
    requested: dict[str, int]
    allocation: dict[str, int]
    priority: dict[str, float]

    @staticmethod
    def from_result(result: CRResult) -> "CRResultOut":
        return CRResultOut(
            requested=_pair_dict_to_str(result.requested),
            allocation=_pair_dict_to_str(result.allocation),
            priority=_pair_dict_to_str(result.priority),
        )


class ComparisonOut(BaseModel):
    scenario_id: str
    auction: AuctionResultOut
    auction_metrics: MetricsOut
    cr: CRResultOut
    cr_metrics: MetricsOut
