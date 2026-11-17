/** O turno e o horário de cada turma — o espelho de
 * `equations.class_shift` e `equations.class_schedule`.
 *
 *     N = ⌊k / 3⌋ turmas noturnas,  D = k − N diurnas
 *     n-ésima turma de um turno → horário (n mod |slots|) + 1
 *
 * A varredura é na ordem da grade — período, disciplina, turma, com as
 * optativas no fim —, e é dela que sai o equilíbrio: o número de turmas por
 * horário difere em no máximo 1.
 *
 * A tela faz esta conta sozinha porque o formulário precisa dizer quanta
 * turma cai em cada horário **antes** de existir execução a quem perguntar —
 * é esse número que diz se mexer nos horários apertou o conflito.
 */
import type { DisciplineInput } from "../types";

export const DAY = "day";
export const NIGHT = "night";

export function classShifts(count: number): string[] {
  if (count <= 0) return [];
  const night = Math.floor(count / 3);
  return [
    ...Array.from({ length: count - night }, () => DAY),
    ...Array.from({ length: night }, () => NIGHT),
  ];
}

/** Quantas turmas caem em cada horário, por turno. Devolve a contagem de
 * cada horário, na ordem deles. */
export function schedulePressure(
  disciplines: DisciplineInput[],
  daySlots: number,
  nightSlots: number
): { day: number[]; night: number[] } {
  const slots = { day: Math.max(daySlots, 1), night: Math.max(nightSlots, 1) };
  const load = {
    day: Array.from({ length: slots.day }, () => 0),
    night: Array.from({ length: slots.night }, () => 0),
  };
  const seen = { day: 0, night: 0 };
  for (const discipline of disciplines) {
    for (const shift of classShifts(discipline.classes)) {
      const turno = shift === NIGHT ? "night" : "day";
      load[turno][seen[turno] % slots[turno]] += 1;
      seen[turno] += 1;
    }
  }
  return load;
}
