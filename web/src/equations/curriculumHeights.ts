/** A altura de cada disciplina na DAG de sucessores.
 *
 *     s_x = 0                                 se x não desbloqueia nada
 *     s_x = 1 + max_{y ∈ unlocks(x)} s_y      caso contrário
 *
 * O comprimento da cadeia mais longa **à frente** da disciplina. Espelha
 * `equations.curriculum_height`, onde ela entra na invariante de preferência.
 */
import { induct } from "./induct";

/** Sentinela da altura. `CYCLIC` dos períodos é 0 porque o período real
 * começa em 1; aqui a altura 0 é um terminal legítimo, então o ciclo não pode
 * reusar esse número. */
export const HEIGHT_CYCLE = -1;

export function curriculumHeights(
  unlocks: Map<string, string[]>
): Record<string, number> {
  return induct(unlocks, {
    combine: (successors) => 1 + Math.max(-1, ...successors),
    cycleValue: HEIGHT_CYCLE,
  });
}
