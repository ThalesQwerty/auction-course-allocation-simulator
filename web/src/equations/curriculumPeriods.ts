/** O período de cada disciplina na grade, induzido dos pré-requisitos */
import { induct } from "./induct";

/** Período de uma disciplina presa num ciclo de sucessores, ou que depende de uma que esteja */
export const CYCLIC = 0;

export function curriculumPeriods(
  prerequisites: Map<string, string[]>
): Record<string, number> {
  return induct(prerequisites, {
    combine: (predecessors) => 1 + Math.max(0, ...predecessors),
    cycleValue: CYCLIC,
  });
}
