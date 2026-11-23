/** Quantos calouros cabem em cada turma de uma disciplina de entrada — os
 * blocos de `equations.entry_class`, do lado do motor.
 *
 * É esta contagem, e não a coorte inteira, que a oferta de uma turma precisa
 * comportar: a matrícula garantida reparte a coorte entre as turmas.
 *
 * O **tamanho da coorte** não mora mais aqui: ele é digitado
 * (`students_per_period`) desde 19/11/2026. Era derivado do produto das
 * combinações de perfil, e mexer num eixo mudava a população sem que ninguém
 * pedisse.
 */
export function entryClassLoad(cohort: number, classes: number): number[] {
  const load = Array.from({ length: Math.max(classes, 0) }, () => 0);
  for (let ordinal = 0; ordinal < Math.max(cohort, 0); ordinal += 1) {
    const block = Math.min(Math.floor((ordinal * classes) / cohort), classes - 1);
    load[block] += 1;
  }
  return load;
}
