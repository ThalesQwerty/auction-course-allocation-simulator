// Espelha src/leilao/api/schemas.py

export interface AgentInput {
  id: string;
  capacity: number; // W_a — carga horária máxima do aluno
  budget: number; // C_a — orçamento inicial de créditos
}

export interface GoodInput {
  id: string;
  quantity: number; // q_x — vagas na disciplina
  weight: number; // w_x — carga horária da disciplina
}

export interface BidInput {
  agent_id: string;
  good_id: string;
  credits: number; // c_{a,x} — créditos apostados no lance
}

export interface RunRequest {
  agents: AgentInput[];
  goods: GoodInput[];
  bids: BidInput[];
  exclusions: string[][]; // cliques de choque de horário
  seed: number;
}

export interface RunResponse {
  allocation: Record<string, number>; // "agent_id|good_id" -> 0/1
  prices: Record<string, number>; // good_id -> preço (sempre inteiro: créditos são inteiros)
  consumption: Record<string, number>; // "agent_id|good_id" -> créditos consumidos (inteiro)
  remaining_budget: Record<string, number>; // agent_id -> créditos restantes (inteiro)
}

export function emptyScenario(): RunRequest {
  return { agents: [], goods: [], bids: [], exclusions: [], seed: 0 };
}
