import { GUARANTEED_ROUND } from "../types";
import type { OutcomeLabel, RequestRow } from "../types";

/** O que aconteceu com uma linha **naquela rodada** */
export type Tone = "approved" | "failed" | "refused" | "dropped" | "idle";

export interface Outcome {
  label: OutcomeLabel;
  tone: Tone;
   /** A vaga que não veio de rodada nenhuma: a matrícula garantida do ingressante, concedida antes de o leilão abrir */
  guaranteed: boolean;
}

/** O resultado de uma turma **nesta** rodada, ou `null` quando ela não é linha de tabela aqui */
export function outcomeOf(record: RequestRow, round: number): Outcome | null {
  const won = record.rodada_ganha;
  const guaranteed = won === GUARANTEED_ROUND;
  const settled = won !== null && (won === round || (guaranteed && round === 1));
  if (settled) {
    if (record.excluida) return { label: "excluída", tone: "dropped", guaranteed };
    return record.aprovada
      ? { label: "aprovada", tone: "approved", guaranteed }
      : { label: "reprovada", tone: "failed", guaranteed };
  }
  if ((record.lances[round - 1] ?? 0) > 0)
    return { label: "indeferida", tone: "refused", guaranteed: false };
  if (won !== null && (guaranteed || won < round)) return null;
  return { label: "não solicitada", tone: "idle", guaranteed: false };
}

/** As rodadas que renderam linha, de 1 a `rounds`: a vazia não vira bloco */
export const roundsWith = (
  rounds: number,
  has: (round: number) => boolean
): number[] =>
  Array.from({ length: rounds }, (_, index) => index + 1).filter(has);
