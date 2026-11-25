/** O tamanho da coorte — `config.students_per_period`, do lado do motor */
export function cohortSize(entrantsPerClass: number, entryClasses: number): number {
  return Math.max(entrantsPerClass, 0) * Math.max(entryClasses, 0);
}
