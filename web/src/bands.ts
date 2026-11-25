/** As séries da comparação, régua por recorte: de onde vêm e com que cor saem */
import type { SeriesGroupStyle } from "./charts";
import { boxStats, requestFunnel } from "./equations";
import { bandColor } from "./profileColors";
import type {
  ArmResult,
  AxisBands,
  Band,
  CutAxis,
  GroupBands,
  Ruler,
  RunSummary,
} from "./types";

/** O eixo X **colapsado**: uma caixa por modelo, sobre as seeds, em vez de uma linha ao longo do tempo */
export const AGGREGATE = "aggregate";

export type RulerChoice = Ruler | typeof AGGREGATE;

/** As réguas na ordem do seletor, com o rótulo e como o eixo X se lê */
export const RULERS: {
  ruler: Ruler;
  label: string;
  point: (x: number) => string;
  weight: string;
}[] = [
  {
    ruler: "period",
    label: "Período global",
    point: (x) => `Período ${x}`,
    weight: "Alunos medidos",
  },
  {
    ruler: "age",
    label: "Período local",
    point: (x) => `${x}º período do aluno`,
    weight: "Alunos que chegaram à idade",
  },
];

/** O que o seletor de linhas oferece */
export type CutChoice = CutAxis;

/** Os recortes na ordem do seletor, com o rótulo da tela, o campo de cortes do cenário e o domínio em que esses cortes valem */
export const CUTS: {
  axis: CutChoice;
  label: string;
  field?: "grade_cuts" | "reserve_cuts";
  domain?: [number, number];
  decimals?: number;
  step?: number;
}[] = [
  { axis: "overall", label: "Geral" },
  {
    axis: "grade_average",
    label: "CR",
    field: "grade_cuts",
    domain: [0, 10],
    decimals: 1,
    step: 0.1,
  },
  {
    axis: "reserve",
    label: "Utilidade de reserva",
    field: "reserve_cuts",
    domain: [0, 1],
    decimals: 3,
    step: 0.001,
  },
];

/** O domínio em que os cortes de um eixo valem */
export function cutDomain(axis: CutChoice): [number, number] | null {
  return CUTS.find((option) => option.axis === axis)?.domain ?? null;
}

const STATE_KEYS = [
  "not_eligible",
  "not_requested",
  "refused",
  "excluded",
  "failed",
  "approved",
] as const;

/** Os pontos do eixo de um grupo */
export const pointsOf = (group: GroupBands): number[] =>
  group.x ?? group.period ?? [];

export const rulerOf = (axis: AxisBands): Ruler => axis.ruler ?? "period";

/** O recorte "Geral" de uma comparação antiga, refeito a partir da série por período de cada simulação — a mesma redução que a API faz hoje */
function legacyBands(runs: RunSummary[]): AxisBands[] {
  const rows = new Map<number, Record<string, number | null>[]>();
  runs.forEach((run) => {
    const series = run.by_period;
    if (!series) return;
    series.period.forEach((period, i) => {
      const row: Record<string, number | null> = {
        students: series.students[i],
        efficiency: series.efficiency[i],
        attendance: series.attendance?.[i] ?? null,
        mean_round: series.mean_round?.[i] ?? null,
        fidelity: series.fidelity[i],
        fairness: series.fairness[i],
        grade_average: series.grade_average?.[i] ?? null,
        credits_supply: series.credits_supply?.[i] ?? null,
        credits_spent: series.credits_spent?.[i] ?? null,
        credits_returned: series.credits_returned?.[i] ?? null,
        exclusion_rate: series.exclusion_rate?.[i] ?? null,
      };
      const states = series.request_states?.[i];
      STATE_KEYS.forEach((key) => (row[key] = states?.[key] ?? null));
      if (states) Object.assign(row, requestFunnel(states));
      series.allocations_per_round?.[i]?.forEach(
        (value, r) => (row[`round_${r + 1}`] = value)
      );
      const bucket = rows.get(period);
      if (bucket) bucket.push(row);
      else rows.set(period, [row]);
    });
  });
  if (!rows.size) return [];

  const periods = [...rows.keys()].sort((a, b) => a - b);
  const keys = [...new Set(periods.flatMap((p) => rows.get(p)!.flatMap(Object.keys)))];
  const band = (period: number, key: string): Band | null => {
    const stats = boxStats(
      rows
        .get(period)!
        .map((row) => row[key])
        .filter((v): v is number => v !== null && v !== undefined)
    );
    return stats ? [stats.q1, stats.median, stats.q3] : null;
  };
  const overall: GroupBands = {
    group: "overall",
    x: periods,
    n: periods.map((p) => rows.get(p)!.length),
    values: Object.fromEntries(keys.map((key) => [key, periods.map((p) => band(p, key))])),
  };
  return [{ ruler: "period", axis: "overall", groups: [overall] }];
}

export const seriesOf = (arm: ArmResult | undefined): AxisBands[] =>
  arm ? (arm.series ?? legacyBands(arm.runs)) : [];

export function cutGroups(
  cut: CutAxis,
  present: string[],
  palette: { solo: string; bands?: (string | undefined)[] }
): SeriesGroupStyle[] {
  if (cut === "overall") {
    return [{ key: "overall", label: "Geral", color: palette.solo }];
  }
  const bands = Math.max(present.length, 1);
  return present.map((key, index) => ({
    key,
    label: key,
    color: palette.bands?.[index] ?? bandColor(index, bands),
  }));
}
