/** O período de cada disciplina na grade, induzido dos pré-requisitos.
 *
 *     p_x = 1                               se ninguém desbloqueia x
 *     p_x = 1 + max_{y ∈ requires(x)} p_y   caso contrário
 *
 * Espelha `equations.curriculum_period`. A conta é duplicada de propósito: a
 * tela mostra o período enquanto o usuário edita, antes de existir execução a
 * quem perguntar.
 */
import { induct } from "./induct";

/** Período de uma disciplina presa num ciclo de sucessores, ou que depende de
 * uma que esteja. Não é período nenhum — ela nunca ficaria elegível. É 0
 * porque o período real começa em 1. */
export const CYCLIC = 0;

export function curriculumPeriods(
  prerequisites: Map<string, string[]>
): Record<string, number> {
  return induct(prerequisites, {
    combine: (predecessors) => 1 + Math.max(0, ...predecessors),
    cycleValue: CYCLIC,
  });
}
