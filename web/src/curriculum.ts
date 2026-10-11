import type { DisciplineInput } from "./types";

/** Aceita grade nova (`unlocks`) ou legada (`prerequisites`) e devolve sempre
 * sucessores. Usado ao reler o histórico do navegador. */
export function withUnlocks(
  disciplines: Array<
    Omit<DisciplineInput, "unlocks"> & { unlocks?: string[]; prerequisites?: string[] }
  >
): DisciplineInput[] {
  if (disciplines.every((d) => Array.isArray(d.unlocks))) {
    return disciplines.map(({ name, seats, hours, unlocks }) => ({
      name,
      seats,
      hours,
      unlocks: unlocks ?? [],
    }));
  }
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

/** Altura \(s_x\) na DAG de sucessores: 0 se não desbloqueia nada; senão
 * \(1 + \max\) das alturas dos sucessores. Espelha `SimulationConfig.heights`. */
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
        height[name] = successors.some((s) => height[s] === CYCLIC)
          ? CYCLIC
          : 1 + Math.max(-1, ...successors.map((s) => height[s]));
        continue;
      }
      if (height[name] !== undefined) continue;
      if (onPath.has(name)) {
        height[name] = CYCLIC;
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

/** As disciplinas de 1º período, na ordem do cenário: a matrícula garantida
 * de quem ingressa. */
export function firstPeriodDisciplines(disciplines: DisciplineInput[]): DisciplineInput[] {
  const period = curriculumPeriods(disciplines);
  return disciplines.filter((d) => period[d.name] === 1);
}

/** Quantos períodos a grade tem — o maior período alcançado. 0 quando toda a
 * grade está presa num ciclo. */
export function curriculumLength(disciplines: DisciplineInput[]): number {
  const values = Object.values(curriculumPeriods(disciplines));
  return values.length ? Math.max(0, ...values) : 0;
}
