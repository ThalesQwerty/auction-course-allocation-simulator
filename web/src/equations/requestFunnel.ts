/** O funil de uma solicitação em quatro frações condicionais */
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
