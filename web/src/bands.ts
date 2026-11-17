/** As séries da comparação, régua por recorte: de onde vêm e com que cor saem.
 *
 * Duas escolhas independentes governam um gráfico. A **régua** (`Ruler`) é o
 * eixo X — o período da simulação, a idade do aluno ou a coorte dele —, e o
 * **recorte** (`CutChoice`) são as cores das linhas: um recorte da API, ou a
 * amplitude, que troca a linha por grupo pela linha por eixo. O modelo é a
 * terceira dimensão e não é escolha: ele é sempre o traçado.
 *
 * A API manda cada braço já reduzido entre as seeds, uma entrada por
 * combinação (`ArmResult.series`). Uma comparação gravada antes disso traz só
 * a série por período de cada simulação, e dela sai o recorte "Geral" da régua
 * do período — as outras combinações não têm material, porque reagrupar por
 * idade ou por coorte exige as células, que ali não foram gravadas.
 */
import type { SeriesGroupStyle, SeriesLine } from "./charts";
import { amplitude, boxStats, requestFunnel } from "./equations";
import { PALETTE, profileColor } from "./profileColors";
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

/** O recorte que a API não manda: em vez de uma linha por grupo, uma linha
 * por **eixo**, e o valor é o vão entre os grupos dele. Ele responde outra
 * pergunta — não "quanto cada perfil colheu" mas "quanto o perfil importou" —
 * e por isso é escolha de recorte, e não gráfico à parte. */
export const AMPLITUDE = "amplitude";

/** O que o seletor de linhas oferece: um recorte da API ou a amplitude. */
export type CutChoice = CutAxis | typeof AMPLITUDE;

/** Os recortes na ordem do seletor, com o rótulo da tela. */
export const CUTS: { axis: CutChoice; label: string }[] = [
  { axis: "overall", label: "Geral" },
  { axis: "performance", label: "Desempenho" },
  { axis: "availability", label: "Disponibilidade" },
  { axis: "selectivity", label: "Seletividade" },
  { axis: "routine", label: "Rotina" },
  { axis: AMPLITUDE, label: "Amplitude" },
];

/** A cor de cada eixo na amplitude. Própria e fixa: a linha aqui não é um
 * grupo de gente, então a cor que o cenário deu ao perfil não serve — e o
 * eixo inteiro precisa de uma cor só. */
const AMPLITUDE_COLORS: Record<string, string> = {
  performance: PALETTE.green,
  availability: PALETTE.blue,
  selectivity: PALETTE.yellow,
  routine: PALETTE.red,
};

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

/** As séries de um braço, uma entrada por régua × recorte. */
export const seriesOf = (arm: ArmResult | undefined): AxisBands[] =>
  arm ? (arm.series ?? legacyBands(arm.runs)) : [];

/** Os eixos que a amplitude mede numa régua — os de perfil com pelo menos
 * dois grupos presentes. Com um grupo só não há vão, e a linha seria uma reta
 * em zero dizendo que o eixo não separa ninguém.
 *
 * `axes` são os eixos **já filtrados pela régua**, de todos os braços juntos:
 * o que está presente é o mesmo dos dois lados. */
export const amplitudeGroups = (axes: AxisBands[]): SeriesGroupStyle[] =>
  CUTS.filter(
    (cut) =>
      AMPLITUDE_COLORS[cut.axis] &&
      axes.some((entry) => entry.axis === cut.axis && entry.groups.length > 1)
  ).map((cut) => ({
    key: cut.axis,
    label: cut.label,
    color: AMPLITUDE_COLORS[cut.axis],
  }));

/** As linhas da amplitude de um braço: por eixo de perfil, o vão entre as
 * medianas dos grupos dele em cada ponto da régua (`equations.amplitude`).
 *
 * O ponto não leva faixa — a amplitude é um número só, e não uma redução
 * entre as seeds. O `n` dele é o **menor** entre os grupos que entraram no
 * vão: a amplitude só está tão medida quanto o grupo mais escasso dela. */
export const amplitudeLines = (
  axes: AxisBands[],
  arm: string,
  key: string
): SeriesLine[] =>
  amplitudeGroups(axes).map((style) => {
    const medians = new Map<number, { values: number[]; n: number }>();
    axes
      .filter((entry) => entry.axis === style.key)
      .flatMap((entry) => entry.groups)
      .forEach((group) =>
        pointsOf(group).forEach((x, i) => {
          const band = group.values[key]?.[i];
          if (!band) return;
          const found = medians.get(x);
          if (found) {
            found.values.push(band[1]);
            found.n = Math.min(found.n, group.n[i] ?? 0);
          } else medians.set(x, { values: [band[1]], n: group.n[i] ?? 0 });
        })
      );
    return {
      arm,
      group: style.key,
      points: [...medians.entries()]
        .sort((left, right) => left[0] - right[0])
        .flatMap(([x, entry]) => {
          const span = amplitude(entry.values);
          return span === null ? [] : [{ x, median: span, n: entry.n }];
        }),
    };
  });

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
      routine: config.routine_profiles,
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
