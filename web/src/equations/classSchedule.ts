/** O horário de cada turma — o espelho de `equations.class_schedule` */
import type { DisciplineInput } from "../types";

export function schedulePressure(
  disciplines: DisciplineInput[],
  slots: number
): number[] {
  const total = Math.max(slots, 1);
  const load = Array.from({ length: total }, () => 0);
  let seen = 0;
  for (const discipline of disciplines) {
    for (let index = 0; index < discipline.classes; index += 1) {
      load[seen % total] += 1;
      seen += 1;
    }
  }
  return load;
}
