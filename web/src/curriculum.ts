/** Leitura da grade no navegador: migração do formato antigo e os recortes que as telas usam */
import { CYCLIC, curriculumPeriods as inducePeriods } from "./equations";
import type { DisciplineInput } from "./types";

export { CYCLIC };

type Unlocked = Omit<DisciplineInput, "entry">;

type StoredDiscipline = Omit<DisciplineInput, "unlocks" | "entry"> & {
  unlocks?: string[];
  prerequisites?: string[];
  entry?: boolean;
};

/** Aceita grade nova (`unlocks`) ou legada (`prerequisites`) */
export function withUnlocks(disciplines: StoredDiscipline[]): DisciplineInput[] {
  const normalized = disciplines.every((d) => Array.isArray(d.unlocks))
    ? disciplines.map(({ name, classes, hours, unlocks }) => ({
        name,
        classes,
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

/** Inverte a grade legada: cada disciplina declarava o que exigia, e hoje declara o que destrava */
function fromPrerequisites(disciplines: StoredDiscipline[]): Unlocked[] {
  const unlocks = new Map(disciplines.map((d) => [d.name, [] as string[]]));
  for (const discipline of disciplines) {
    for (const predecessor of discipline.prerequisites ?? []) {
      unlocks.get(predecessor)?.push(discipline.name);
    }
  }
  return disciplines.map(({ name, classes, hours }) => ({
    name,
    classes,
    hours,
    unlocks: unlocks.get(name) ?? [],
  }));
}

/** Predecessores de cada disciplina — a aresta inversa de `unlocks` */
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

export function curriculumPeriods(
  disciplines: DisciplineInput[]
): Record<string, number> {
  return inducePeriods(predecessorsByDiscipline(disciplines));
}

/** As disciplinas de entrada: a matrícula garantida de quem ingressa */
export function entryDisciplines(disciplines: DisciplineInput[]): DisciplineInput[] {
  return disciplines.filter((d) => d.entry);
}

/** Em quantas turmas cada disciplina de entrada está repartida — o fator que leva o ingresso por turma à coorte (`equations.cohortSize`) */
export function entryClasses(disciplines: DisciplineInput[]): number {
  return entryDisciplines(disciplines)[0]?.classes ?? 0;
}
