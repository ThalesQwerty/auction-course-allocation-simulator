/** Leitura da grade no navegador: migração do formato antigo e os recortes
 * que as telas usam.
 *
 * As duas induções — período e altura — estão em `equations/`, porque são
 * fórmulas que espelham o motor. Aqui fica o que é só do front: converter o
 * que o `localStorage` guardou e montar as arestas que elas consomem.
 */
import { CYCLIC, curriculumPeriods as inducePeriods } from "./equations";
import type { DisciplineInput } from "./types";

export { CYCLIC };

/** A grade já com os sucessores, antes de a flag de entrada ser resolvida. */
type Unlocked = Omit<DisciplineInput, "entry">;

type StoredDiscipline = Omit<DisciplineInput, "unlocks" | "entry"> & {
  unlocks?: string[];
  prerequisites?: string[];
  entry?: boolean;
};

/** Aceita grade nova (`unlocks`) ou legada (`prerequisites`). Campo `entry`
 * ausente vale verdadeiro nas raízes — o que o histórico antigo chamava de
 * 1º período. */
export function withUnlocks(disciplines: StoredDiscipline[]): DisciplineInput[] {
  const normalized = disciplines.every((d) => Array.isArray(d.unlocks))
    ? disciplines.map(({ name, seats, hours, unlocks }) => ({
        name,
        seats,
        hours,
        unlocks: unlocks ?? [],
      }))
    : fromPrerequisites(disciplines);

  const predecessors = predecessorsByDiscipline(normalized);
  return normalized.map((discipline, index) => ({
    ...discipline,
    entry:
      disciplines[index].entry ?? (predecessors.get(discipline.name)?.length ?? 0) === 0,
  }));
}

/** Inverte a grade legada: cada disciplina declarava o que exigia, e hoje
 * declara o que destrava. */
function fromPrerequisites(disciplines: StoredDiscipline[]): Unlocked[] {
  const unlocks = new Map(disciplines.map((d) => [d.name, [] as string[]]));
  for (const discipline of disciplines) {
    for (const predecessor of discipline.prerequisites ?? []) {
      unlocks.get(predecessor)?.push(discipline.name);
    }
  }
  return disciplines.map(({ name, seats, hours }) => ({
    name,
    seats,
    hours,
    unlocks: unlocks.get(name) ?? [],
  }));
}

/** Predecessores de cada disciplina — a aresta inversa de `unlocks`. Sucessor
 * apontando para disciplina inexistente é ignorado: é o estado de uma
 * renomeação a meio. */
function predecessorsByDiscipline(
  disciplines: readonly { name: string; unlocks: string[] }[]
): Map<string, string[]> {
  const known = new Set(disciplines.map((d) => d.name));
  const predecessors = new Map(disciplines.map((d) => [d.name, [] as string[]]));
  for (const discipline of disciplines) {
    for (const successor of discipline.unlocks) {
      if (successor === discipline.name || !known.has(successor)) continue;
      predecessors.get(successor)!.push(discipline.name);
    }
  }
  return predecessors;
}

/** O período de cada disciplina — ver `equations.curriculumPeriods`. */
export function curriculumPeriods(
  disciplines: DisciplineInput[]
): Record<string, number> {
  return inducePeriods(predecessorsByDiscipline(disciplines));
}

/** As disciplinas de entrada: a matrícula garantida de quem ingressa. Vem da
 * flag, e **não** de não ter pré-requisito — a optativa também não tem e não
 * é entrada. É este conjunto que dimensiona `students_per_period` e
 * `max_hours`. Espelha `SimulationConfig.entry_disciplines`. */
export function entryDisciplines(disciplines: DisciplineInput[]): DisciplineInput[] {
  return disciplines.filter((d) => d.entry);
}
