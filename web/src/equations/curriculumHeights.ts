/** A altura de cada disciplina na DAG de sucessores */
import { induct } from "./induct";

/** Sentinela da altura */
export const HEIGHT_CYCLE = -1;

export function curriculumHeights(
  unlocks: Map<string, string[]>
): Record<string, number> {
  return induct(unlocks, {
    combine: (successors) => 1 + Math.max(-1, ...successors),
    cycleValue: HEIGHT_CYCLE,
  });
}
