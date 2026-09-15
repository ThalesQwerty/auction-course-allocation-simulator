"""Cenário de entrada unificado, construído pela interface e consumido pelo motor.

Um Scenario contém tudo que é necessário para rodar AMBOS os mecanismos
(leilão por créditos e linha de base por CR) sobre a mesma instância de
alunos/disciplinas, garantindo a comparação controlada exigida pela
metodologia (Seção 7.3): "sempre que os mecanismos forem comparados entre si,
ambos serão inicializados com a mesma configuração de parâmetros iniciais".
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .auction import AuctionAgent, AuctionConfig, AuctionDemand, AuctionGood
from .cr_mechanism import CRAgent, CRConfig, CRDemandCandidate, CRGood
from .entities import Good, MutualExclusion

_BIAS_KEY_SEP = "|"


@dataclass
class ScenarioAgent:
    id: str
    capacity: float  # W_a — carga horária máxima do estudante
    budget: int  # C_a^(1) — orçamento inicial de créditos (leilão)
    academic_index: float  # N_a — Coeficiente de Rendimento (linha de base)


@dataclass
class ScenarioGood:
    id: str
    quantity: int  # q_x — vagas na disciplina
    weight: float  # w_x — carga horária da disciplina


@dataclass
class ScenarioDemand:
    agent_id: str
    good_id: str
    utility: float  # u_{a,x} in [0, 1] — utilidade percebida, guia ambos os mecanismos


@dataclass
class Scenario:
    id: str
    name: str
    agents: list[ScenarioAgent] = field(default_factory=list)
    goods: list[ScenarioGood] = field(default_factory=list)
    demands: list[ScenarioDemand] = field(default_factory=list)
    exclusions: list[list[str]] = field(default_factory=list)  # cliques de choque de horário
    tie_break_order: dict[str, list[str]] = field(default_factory=dict)  # good_id -> ordem de agentes
    bias: dict[str, int] = field(default_factory=dict)  # "agent_id|good_id" -> beta bruto
    num_rounds: int = 1
    seed: int = 0

    # -- conversões de/para os dois mecanismos -----------------------------

    def to_auction_config(self) -> AuctionConfig:
        return AuctionConfig(
            agents=[AuctionAgent(a.id, a.capacity, a.budget) for a in self.agents],
            goods=[AuctionGood(g.id, g.quantity, g.weight) for g in self.goods],
            demands=[AuctionDemand(d.agent_id, d.good_id, d.utility) for d in self.demands],
            exclusions=[MutualExclusion(frozenset(clique)) for clique in self.exclusions],
            num_rounds=self.num_rounds,
            tie_break_order=dict(self.tie_break_order),
            bias=self._bias_as_tuples(),
            seed=self.seed,
        )

    def to_cr_config(self) -> CRConfig:
        return CRConfig(
            agents=[CRAgent(a.id, a.capacity, a.academic_index) for a in self.agents],
            goods=[CRGood(g.id, g.quantity, g.weight) for g in self.goods],
            demands=[CRDemandCandidate(d.agent_id, d.good_id, d.utility) for d in self.demands],
            exclusions=[MutualExclusion(frozenset(clique)) for clique in self.exclusions],
            seed=self.seed,
        )

    def goods_entities(self) -> list[Good]:
        return [Good(g.id, g.quantity, g.weight) for g in self.goods]

    def utilities_by_pair(self) -> dict[tuple[str, str], float]:
        return {(d.agent_id, d.good_id): d.utility for d in self.demands}

    def academic_index_by_agent(self) -> dict[str, float]:
        return {a.id: a.academic_index for a in self.agents}

    def _bias_as_tuples(self) -> dict[tuple[str, str], int]:
        result: dict[tuple[str, str], int] = {}
        for key, value in self.bias.items():
            agent_id, good_id = key.split(_BIAS_KEY_SEP, 1)
            result[(agent_id, good_id)] = value
        return result

    # -- (de)serialização JSON ----------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Scenario":
        return Scenario(
            id=data["id"],
            name=data["name"],
            agents=[ScenarioAgent(**a) for a in data.get("agents", [])],
            goods=[ScenarioGood(**g) for g in data.get("goods", [])],
            demands=[ScenarioDemand(**d) for d in data.get("demands", [])],
            exclusions=[list(c) for c in data.get("exclusions", [])],
            tie_break_order=dict(data.get("tie_break_order", {})),
            bias=dict(data.get("bias", {})),
            num_rounds=data.get("num_rounds", 1),
            seed=data.get("seed", 0),
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "Scenario":
        return Scenario.from_dict(json.loads(path.read_text(encoding="utf-8")))
