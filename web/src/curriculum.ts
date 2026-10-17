import type { DisciplineInput } from "./types";

/** Período de uma disciplina que está dentro de um ciclo de pré-requisitos, ou
 * que depende de uma que esteja. Não é período nenhum: a disciplina nunca
 * ficaria elegível. O motor rejeita o cenário; a tela de configuração precisa
 * sobreviver a ele, porque um ciclo é o estado normal do formulário no meio de
 * uma edição. */
export const CYCLIC = 0;

/** O período de cada disciplina na grade, por indução sobre os pré-requisitos:
 * sem pré-requisito é 1º período; com pré-requisitos é o maior período entre
 * eles mais um.
 *
 * Espelha `SimulationConfig.curriculum_periods`. A conta é duplicada de
 * propósito: a tela de configuração mostra o período enquanto o usuário edita,
 * antes de existir execução alguma para perguntar ao motor.
 *
 * Pré-requisito que aponta para disciplina inexistente é ignorado — no
 * formulário isso acontece o tempo todo, entre renomear uma disciplina e
 * acertar quem a referencia.
 */
export function curriculumPeriods(disciplines: DisciplineInput[]): Record<string, number> {
  const requires = new Map(
    disciplines.map((d) => [d.name, d.prerequisites.filter((p) => p !== d.name)])
  );
  const period: Record<string, number> = {};
  const onPath = new Set<string>();

  for (const start of requires.keys()) {
    if (period[start] !== undefined) continue;
    const stack: [string, boolean][] = [[start, false]];
    while (stack.length > 0) {
      const [name, expanded] = stack.pop()!;
      if (expanded) {
        onPath.delete(name);
        // Um pré-requisito dentro de um ciclo contamina quem depende dele: sem
        // período para ele, não há "o maior mais um" aqui.
        const prerequisites = requires.get(name) ?? [];
        const known = prerequisites.filter((p) => requires.has(p));
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

/** As **disciplinas de entrada**, na ordem do cenário: a matrícula garantida
 * de quem ingressa.
 *
 * Não é o mesmo que "disciplinas de 1º período". Ser de 1º período sai da
 * indução — não ter pré-requisito —, e a **optativa também não tem**, então
 * ela cai no 1º período e não é entrada. É este conjunto, e não o do 1º
 * período, que dimensiona `students_per_period` e `max_hours`. Espelha
 * `SimulationConfig.entry_disciplines`. */
export function entryDisciplines(disciplines: DisciplineInput[]): DisciplineInput[] {
  const period = curriculumPeriods(disciplines);
  return disciplines.filter((d) => period[d.name] === 1 && !d.elective);
}

/** Quantos períodos a grade tem — o maior período alcançado. 0 quando toda a
 * grade está presa num ciclo. */
export function curriculumLength(disciplines: DisciplineInput[]): number {
  const values = Object.values(curriculumPeriods(disciplines));
  return values.length ? Math.max(0, ...values) : 0;
}
