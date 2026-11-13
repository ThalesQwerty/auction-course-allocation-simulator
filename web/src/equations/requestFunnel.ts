/** O funil de uma solicitação em quatro frações condicionais.
 *
 *     solicitadas = (todas − não solicitadas − não elegíveis) / todas
 *     deferidas   = (aprovadas + reprovadas + excluídas) / solicitadas
 *     cursadas    = (aprovadas + reprovadas) / deferidas
 *     aprovadas   = aprovadas / cursadas
 *
 * Espelha `equations.request_funnel`, e está aqui pelo mesmo motivo que as
 * outras contas duplicadas: a comparação gravada antes de 11/11/2026 não traz
 * as frações, só as seis contagens, e é desta função que o recorte "Geral"
 * dessas execuções antigas sai (`legacyBands`).
 *
 * `null` quando o nó está vazio, nunca 0: "ninguém pediu nada" é diferente de
 * "ninguém foi deferido".
 */
import type { RequestStates } from "../types";

export interface RequestFunnel {
  requested_share: number | null;
  granted_share: number | null;
  attended_share: number | null;
  approved_share: number | null;
}

const share = (part: number, whole: number) => (whole > 0 ? part / whole : null);

export function requestFunnel(states: RequestStates): RequestFunnel {
  const requested =
    states.refused + states.excluded + states.failed + states.approved;
  const granted = states.excluded + states.failed + states.approved;
  const attended = states.failed + states.approved;
  const total = requested + states.not_eligible + states.not_requested;
  return {
    requested_share: share(requested, total),
    granted_share: share(granted, requested),
    attended_share: share(attended, granted),
    approved_share: share(states.approved, attended),
  };
}
