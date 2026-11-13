/** As séries da comparação, régua por recorte: de onde vêm e com que cor saem.
 *
 * Duas escolhas independentes governam um gráfico. A **régua** (`Ruler`) é o
 * eixo X — o período da simulação, a idade do aluno ou a coorte dele —, e o
 * **recorte** (`CutAxis`) são as cores das linhas. O modelo é a terceira
 * dimensão e não é escolha: ele é sempre o traçado.
 *
 * A API manda cada braço já reduzido entre as seeds, uma entrada por
 * combinação (`ArmResult.series`). Uma comparação gravada antes disso traz só
 * a série por período de cada simulação, e dela sai o recorte "Geral" da régua
 * do período — as outras combinações não têm material, porque reagrupar por
 * idade ou por coorte exige as células, que ali não foram gravadas.
 */
import type { SeriesGroupStyle } from "./charts";
import { boxStats, requestFunnel } from "./equations";
import { profileColor } from "./profileColors";
import type {
  ArmResult,
  AxisBands,
  Band,
  CompareRequest,
  CutAxis,
  GroupBands,
  Ruler,
  RunSummary,
} from "./types";

/** As réguas na ordem do seletor, com o rótulo e como o eixo X se lê. */
export const RULERS: {
  ruler: Ruler;
  label: string;
  /** O rótulo de um ponto, no tooltip e no eixo. */
  point: (x: number) => string;
  /** O que a contagem de alunos conta nesta régua — ver `RulerSeries`. */
  weight: string;
}[] = [
  {
    ruler: "period",
    label: "Período",
    point: (x) => `Período ${x}`,
    weight: "Alunos medidos",
  },
  {
    ruler: "age",
    label: "Idade",
    point: (x) => `${x}º período do aluno`,
    weight: "Alunos que chegaram à idade",
  },
  {
    ruler: "cohort",
    label: "Coorte",
    point: (x) => `Coorte ${x}`,
    weight: "Aluno-períodos medidos",
  },
];

/** Os recortes na ordem do seletor, com o rótulo da tela. */
export const CUTS: { axis: CutAxis; label: string }[] = [
  { axis: "overall", label: "Geral" },
  { axis: "performance", label: "Desempenho" },
  { axis: "availability", label: "Disponibilidade" },
  { axis: "selectivity", label: "Seletividade" },
  { axis: "concentration", label: "Concentração" },
];

const STATE_KEYS = [
  "not_eligible",
  "not_requested",
  "refused",
  "excluded",
  "failed",
  "approved",
] as const;

/** Os pontos do eixo de um grupo. `period` é o nome que o campo tinha antes de
 * a régua ser escolha, e comparação gravada até 11/11/2026 traz aquele. */
export const pointsOf = (group: GroupBands): number[] =>
  group.x ?? group.period ?? [];

/** A régua de um eixo. Ausente, é a do período — era a única. */
export const rulerOf = (axis: AxisBands): Ruler => axis.ruler ?? "period";

/** O recorte "Geral" de uma comparação antiga, refeito a partir da série por
 * período de cada simulação — a mesma redução que a API faz hoje. */
function legacyBands(runs: RunSummary[]): AxisBands[] {
  const rows = new Map<number, Record<string, number | null>[]>();
  runs.forEach((run) => {
    const series = run.by_period;
    if (!series) return;
    series.period.forEach((period, i) => {
      const row: Record<string, number | null> = {
        students: series.students[i],
        efficiency: series.efficiency[i],
        utilization: series.utilization[i],
        fidelity: series.fidelity[i],
        fairness: series.fairness[i],
        correlation: series.correlation[i],
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

/** As séries de um braço, uma entrada por régua × recorte. */
export const seriesOf = (arm: ArmResult | undefined): AxisBands[] =>
  arm ? (arm.series ?? legacyBands(arm.runs)) : [];

/** Os grupos de um recorte com a cor e o rótulo da tela.
 *
 * Os de perfil saem do cenário que rodou, na ordem e com a cor que ele
 * declarou; o "Geral", a matiz única das séries solitárias. Grupo presente nos
 * dados e ausente do cenário (não deveria haver) entra com a cor de reserva.
 */
export function cutGroups(
  cut: CutAxis,
  config: CompareRequest,
  present: string[],
  palette: { solo: string }
): SeriesGroupStyle[] {
  if (cut === "overall") {
    return [{ key: "overall", label: "Geral", color: palette.solo }];
  }
  const declared: { name: string; color?: string }[] =
    {
      performance: config.performance_profiles,
      availability: config.availability_profiles,
      selectivity: config.selectivity_profiles,
      concentration: config.concentration_profiles,
    }[cut] ?? [];
  const styles = declared.map((profile, index) => ({
    key: profile.name,
    label: profile.name,
    color: profileColor(profile, index),
  }));
  present
    .filter((key) => !styles.some((s) => s.key === key))
    .forEach((key) =>
      styles.push({ key, label: key, color: profileColor({}, styles.length) })
    );
  return styles.filter((s) => present.includes(s.key));
}
