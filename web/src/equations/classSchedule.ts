/** O horário de cada turma — o espelho de `equations.class_schedule`.
 *
 *     n-ésima turma da grade → Horário (n mod |G|) + 1
 *
 * A varredura é na ordem da grade — período, disciplina, turma, com as
 * optativas no fim —, e é dela que sai o equilíbrio: o número de turmas por
 * horário difere em no máximo 1.
 *
 * **Não há turno.** A divisão entre diurno e noturno, e o perfil de rotina
 * que a acompanhava, saíram em 19/11/2026.
 *
 * A tela faz esta conta sozinha porque o formulário precisa dizer quanta
 * turma cai em cada horário **antes** de existir execução a quem perguntar —
 * é esse número que diz se mexer nos horários apertou o conflito.
 */
import type { DisciplineInput } from "../types";

/** Quantas turmas caem em cada horário, na ordem deles. */
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
