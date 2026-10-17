import type { DisciplineInput } from "./types";

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
    : (() => {
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
      })();

  const known = new Set(normalized.map((d) => d.name));
  const predecessors = new Map(normalized.map((d) => [d.name, [] as string[]]));
  for (const discipline of normalized) {
    for (const successor of discipline.unlocks) {
      if (successor !== discipline.name && known.has(successor)) {
        predecessors.get(successor)!.push(discipline.name);
      }
    }
  }
  return normalized.map((discipline, index) => ({
    ...discipline,
    entry:
      disciplines[index].entry ?? (predecessors.get(discipline.name)?.length ?? 0) === 0,
  }));
}

/** Período/altura de uma disciplina que está dentro de um ciclo de sucessores,
 * ou que depende de uma que esteja. Não é período nenhum: a disciplina nunca
 * ficaria elegível. O motor rejeita o cenário; a tela de configuração precisa
 * sobreviver a ele, porque um ciclo é o estado normal do formulário no meio de
 * uma edição. */
export const CYCLIC = 0;

/** Predecessores de cada disciplina — aresta inversa de `unlocks`. Sucessor
 * apontando para disciplina inexistente é ignorado (renomeação a meio). */
function predecessorsByDiscipline(
  disciplines: DisciplineInput[]
): Map<string, string[]> {
  const known = new Set(disciplines.map((d) => d.name));
  const preds = new Map(disciplines.map((d) => [d.name, [] as string[]]));
  for (const discipline of disciplines) {
    for (const successor of discipline.unlocks) {
      if (successor === discipline.name || !known.has(successor)) continue;
      preds.get(successor)!.push(discipline.name);
    }
  }
  return preds;
}

/** O período de cada disciplina na grade, por indução sobre a aresta inversa
 * dos sucessores: quem ninguém desbloqueia é 1º período; quem é desbloqueada
 * por outras é o período seguinte ao mais tardio delas.
 *
 * Espelha `SimulationConfig.curriculum_periods`. A conta é duplicada de
 * propósito: a tela de configuração mostra o período enquanto o usuário edita,
 * antes de existir execução alguma para perguntar ao motor.
 */
export function curriculumPeriods(disciplines: DisciplineInput[]): Record<string, number> {
  const requires = predecessorsByDiscipline(disciplines);
  const period: Record<string, number> = {};
  const onPath = new Set<string>();

  for (const start of requires.keys()) {
    if (period[start] !== undefined) continue;
    const stack: [string, boolean][] = [[start, false]];
    while (stack.length > 0) {
      const [name, expanded] = stack.pop()!;
      if (expanded) {
        onPath.delete(name);
        const parents = requires.get(name) ?? [];
        const known = parents.filter((p) => requires.has(p));
        period[name] = known.some((p) => period[p] === CYCLIC)
          ? CYCLIC
          : 1 + Math.max(0, ...known.map((p) => period[p]));
        continue;
      }
      if (period[name] !== undefined) continue;
      if (onPath.has(name)) {
        period[name] = CYCLIC;
        continue;
      }
      onPath.add(name);
      stack.push([name, true]);
      for (const p of requires.get(name) ?? []) {
        if (requires.has(p)) stack.push([p, false]);
      }
    }
  }
  return period;
}

/** Sentinela da altura. `CYCLIC` é 0 porque o período real começa em 1; a altura
 * 0 é um terminal legítimo, então o ciclo aqui não pode reusar esse número. */
const HEIGHT_CYCLE = -1;

/** Altura s_x na DAG de sucessores: 0 se não desbloqueia nada; senão
 * 1 + max das alturas dos sucessores. Ciclo devolve `HEIGHT_CYCLE`. */
export function curriculumHeights(disciplines: DisciplineInput[]): Record<string, number> {
  const unlocks = new Map(
    disciplines.map((d) => [d.name, d.unlocks.filter((s) => s !== d.name)])
  );
  const height: Record<string, number> = {};
  const onPath = new Set<string>();

  for (const start of unlocks.keys()) {
    if (height[start] !== undefined) continue;
    const stack: [string, boolean][] = [[start, false]];
    while (stack.length > 0) {
      const [name, expanded] = stack.pop()!;
      if (expanded) {
        onPath.delete(name);
        const successors = (unlocks.get(name) ?? []).filter((s) => unlocks.has(s));
        height[name] = successors.some((s) => height[s] === HEIGHT_CYCLE)
          ? HEIGHT_CYCLE
          : 1 + Math.max(-1, ...successors.map((s) => height[s]));
        continue;
      }
      if (height[name] !== undefined) continue;
      if (onPath.has(name)) {
        height[name] = HEIGHT_CYCLE;
        continue;
      }
      onPath.add(name);
      stack.push([name, true]);
      for (const s of unlocks.get(name) ?? []) {
        if (unlocks.has(s)) stack.push([s, false]);
      }
    }
  }
  return height;
}

/** As disciplinas de entrada: a matrícula garantida de quem ingressa. Vem da
 * flag, e não de não ter pré-requisito — a optativa também não tem e não é
 * entrada. É este conjunto que dimensiona `students_per_period` e `max_hours`.
 * Espelha `SimulationConfig.entry_disciplines`. */
export function entryDisciplines(disciplines: DisciplineInput[]): DisciplineInput[] {
  return disciplines.filter((d) => d.entry);

}

/** Quantos períodos a grade tem — o maior período alcançado. 0 quando toda a
 * grade está presa num ciclo. */
export function curriculumLength(disciplines: DisciplineInput[]): number {
  const values = Object.values(curriculumPeriods(disciplines));
  return values.length ? Math.max(0, ...values) : 0;
}
