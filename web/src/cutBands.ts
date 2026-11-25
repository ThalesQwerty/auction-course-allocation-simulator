/** O recorte em faixas, feito aqui a partir das linhas cruas da simulação.
 *
 * As faixas não entram na medição: o motor publica uma linha por (aluno medido,
 * período medido) e esta é a única agregação delas, de modo que mudar um corte
 * não refaz simulação nenhuma. A redução é a mesma do motor — média entre os
 * alunos da faixa num período, mediana e intervalo interquartil entre as seeds.
 */
import { boxStats, jainIndex, valueBand, valueBandNames } from "./equations";
import type { AxisBands, Band, CutAxis, GroupBands, RunSummary } from "./types";

/** As grandezas que a faixa agrega, pela ordem em que os gráficos as pedem */
const KEYS = [
  "students",
  "satisfaction",
  "attendance",
  "progress",
  "fairness",
  "mean_round",
] as const;

/** O que uma faixa acumula num período de uma simulação */
interface Tally {
  satisfaction: number[];
  attendance: number[];
  progress: number[];
  won: number;
  rounds: number;
}

const empty = (): Tally => ({
  satisfaction: [],
  attendance: [],
  progress: [],
  won: 0,
  rounds: 0,
});

const mean = (values: number[]): number =>
  values.reduce((total, value) => total + value, 0) / values.length;

/** As grandezas de uma faixa num período: a mesma agregação de `compute_metrics` */
function measure(tally: Tally): Record<string, number | null> {
  return {
    students: tally.satisfaction.length,
    satisfaction: mean(tally.satisfaction),
    attendance: tally.attendance.length ? mean(tally.attendance) : null,
    progress: mean(tally.progress),
    fairness: jainIndex(tally.satisfaction),
    mean_round: tally.won > 0 ? tally.rounds / tally.won : null,
  };
}

/** Uma simulação recortada: faixa → período → grandezas */
function cutRun(
  run: RunSummary,
  axis: "grade_average" | "reserve",
  cuts: number[],
  names: string[]
): Map<string, Map<number, Record<string, number | null>>> {
  const out = new Map<string, Map<number, Tally>>();
  const rows = run.observations;
  if (rows) {
    const values = rows[axis];
    for (let i = 0; i < rows.period.length; i += 1) {
      const name = names[valueBand(values[i], cuts)];
      const periods = out.get(name) ?? new Map<number, Tally>();
      if (!out.has(name)) out.set(name, periods);
      const tally = periods.get(rows.period[i]) ?? empty();
      if (!periods.has(rows.period[i])) periods.set(rows.period[i], tally);
      tally.satisfaction.push(rows.satisfaction[i]);
      tally.progress.push(rows.progress[i]);
      const seen = rows.attendance[i];
      if (seen !== null) tally.attendance.push(seen);
      const round = rows.mean_round[i];
      if (round !== null) {
        tally.won += rows.won[i];
        tally.rounds += round * rows.won[i];
      }
    }
  }
  return new Map(
    [...out].map(([name, periods]) => [
      name,
      new Map([...periods].map(([period, tally]) => [period, measure(tally)])),
    ])
  );
}

/** As faixas de um eixo, reduzidas entre as seeds — `null` se nada foi medido */
export function cutBands(
  runs: RunSummary[],
  axis: "grade_average" | "reserve",
  cuts: number[],
  domain: [number, number],
  decimals: number
): AxisBands | null {
  if (!runs.some((run) => run.observations?.period.length)) return null;
  const names = valueBandNames(cuts, domain[0], domain[1], decimals);
  const cut = runs.map((run) => cutRun(run, axis, cuts, names));

  const groups: GroupBands[] = [];
  for (const name of names) {
    const periods = [
      ...new Set(cut.flatMap((table) => [...(table.get(name)?.keys() ?? [])])),
    ].sort((a, b) => a - b);
    if (!periods.length) continue;

    const samples = (period: number) =>
      cut.flatMap((table) => {
        const row = table.get(name)?.get(period);
        return row ? [row] : [];
      });
    const band = (period: number, key: string): Band | null => {
      const values = samples(period)
        .map((row) => row[key])
        .filter((value): value is number => value !== null);
      const stats = boxStats(values);
      return stats ? [stats.q1, stats.median, stats.q3] : null;
    };

    groups.push({
      group: name,
      x: periods,
      n: periods.map((period) => samples(period).length),
      values: Object.fromEntries(
        KEYS.map((key) => [key, periods.map((period) => band(period, key))])
      ),
    });
  }
  return groups.length ? { axis: axis as CutAxis, groups } : null;
}
