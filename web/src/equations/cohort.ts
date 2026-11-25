/** O tamanho da coorte — `config.students_per_period`, do lado do motor.
 *
 * O que se digita é o ingresso **por turma de disciplina de entrada**, e a
 * coorte é esse número vezes as turmas de uma dessas disciplinas. Todas elas
 * têm o mesmo número de turmas (o motor recusa a grade em que não têm), então
 * o produto não depende de qual se olha.
 *
 * Era a coorte que se digitava até 24/11/2026, e ela saía repartida entre as
 * turmas em blocos com resto — duas vagas numa turma, uma na vizinha —, de modo
 * que o número digitado não se comparava com a lotação sem refazer a divisão.
 */
export function cohortSize(entrantsPerClass: number, entryClasses: number): number {
  return Math.max(entrantsPerClass, 0) * Math.max(entryClasses, 0);
}
