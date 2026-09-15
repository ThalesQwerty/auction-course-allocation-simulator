// Espelha os schemas Pydantic de src/leilao/api/schemas.py

export interface ScenarioAgent {
  id: string;
  capacity: number; // W_a — carga horária máxima do estudante
  budget: number; // C_a^(1) — orçamento inicial de créditos
  academic_index: number; // N_a — Coeficiente de Rendimento
}

export interface ScenarioGood {
  id: string;
  quantity: number; // q_x — vagas na disciplina
  weight: number; // w_x — carga horária da disciplina
}

export interface ScenarioDemand {
  agent_id: string;
  good_id: string;
  utility: number; // u_{a,x} in (0, 1] — utilidade percebida
}

export interface ScenarioInput {
  name: string;
  agents: ScenarioAgent[];
  goods: ScenarioGood[];
  demands: ScenarioDemand[];
  exclusions: string[][]; // cliques de choque de horário
  tie_break_order: Record<string, string[]>;
  bias: Record<string, number>; // "agent_id|good_id" -> beta bruto
  num_rounds: number;
  seed: number;
}

export interface ScenarioOutput extends ScenarioInput {
  id: string;
}

export interface MetricsOut {
  average_satisfaction: number;
  occupation_rate: number;
  fairness_index: number;
  academic_correlation: number;
  satisfaction_by_agent: Record<string, number>;
}

export interface AuctionRoundOut {
  round_index: number;
  bids: Record<string, number>;
  allocation: Record<string, number>;
  prices: Record<string, number>;
  consumption: Record<string, number>;
}

export interface AuctionResultOut {
  rounds: AuctionRoundOut[];
  final_allocation: Record<string, number>;
  final_consumption: Record<string, number>;
  remaining_budget: Record<string, number>;
}

export interface CRResultOut {
  requested: Record<string, number>;
  allocation: Record<string, number>;
  priority: Record<string, number>;
}

export interface ComparisonOut {
  scenario_id: string;
  auction: AuctionResultOut;
  auction_metrics: MetricsOut;
  cr: CRResultOut;
  cr_metrics: MetricsOut;
}

export function emptyScenario(): ScenarioInput {
  return {
    name: "Novo cenário",
    agents: [],
    goods: [],
    demands: [],
    exclusions: [],
    tie_break_order: {},
    bias: {},
    num_rounds: 1,
    seed: 0,
  };
}
