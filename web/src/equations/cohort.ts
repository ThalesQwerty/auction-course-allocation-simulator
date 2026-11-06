/** O tamanho da coorte, derivado dos perfis.
 *
 *     |A| = exemplares × |desempenho| · |disponibilidade| · |seletividade| · |concentração|
 *
 * A coorte não é digitada: ela sai do número de **combinações de perfil**
 * vezes quantos exemplares de cada uma o cenário pede. É assim que toda
 * combinação recebe o mesmo número de exemplares em toda coorte, sem sobra a
 * girar entre elas — o que tornaria um perfil mais numeroso num período e
 * menos no seguinte, e a diferença entre perfis deixaria de ser do perfil.
 *
 * Espelha `config.SimulationConfig.students_per_period`.
 */
import type { Scenario } from "../types";

type Axes = Pick<
  Scenario,
  | "performance_profiles"
  | "availability_profiles"
  | "selectivity_profiles"
  | "concentration_profiles"
>;

export function profileCombinations(config: Axes): number {
  return (
    config.performance_profiles.length *
    config.availability_profiles.length *
    config.selectivity_profiles.length *
    config.concentration_profiles.length
  );
}

export function cohortSize(
  config: Axes & Pick<Scenario, "students_per_profile">
): number {
  return config.students_per_profile * profileCombinations(config);
}

/** Quantos calouros cabem em cada turma de uma disciplina de entrada — os
 * blocos de `equations.entry_class`, do lado do motor.
 *
 * É esta contagem, e não a coorte inteira, que a oferta de uma turma precisa
 * comportar: a matrícula garantida reparte a coorte entre as turmas. */
export function entryClassLoad(cohort: number, classes: number): number[] {
  const load = Array.from({ length: Math.max(classes, 0) }, () => 0);
  for (let ordinal = 0; ordinal < Math.max(cohort, 0); ordinal += 1) {
    const block = Math.min(Math.floor((ordinal * classes) / cohort), classes - 1);
    load[block] += 1;
  }
  return load;
}
