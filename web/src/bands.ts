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
import type { SeriesGroupStyle } from "./charts";
import { boxStats, requestFunnel } from "./equations";
import { bandColor } from "./profileColors";
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

/** O eixo X **colapsado**: uma caixa por modelo, sobre as seeds, em vez de
 * uma linha ao longo do tempo. Não é régua — é a ausência de uma —, e por
 * isso mora no mesmo seletor delas.
 *
 * A caixa é sobre as **seeds**, e não sobre os alunos: ela responde se o vão
 * entre os mecanismos é maior que o ruído entre populações. A dispersão
 * entre alunos é o que as linhas de quantil mostram, e misturar as duas numa
 * caixa só seria erro de leitura. */
export const AGGREGATE = "aggregate";

/** O que o seletor do eixo X oferece: uma régua da API ou o agregado. */
export type RulerChoice = Ruler | typeof AGGREGATE;

/** As réguas na ordem do seletor, com o rótulo e como o eixo X se lê.
 *
 * A **coorte** saiu em 19/11/2026. Ela só significava algo enquanto havia
 * fases distintas no horizonte — enchimento, regime, drenagem —; na janela
 * estacionária ela e o período dizem a mesma coisa. */
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

/** O que o seletor de linhas oferece. A **amplitude** — uma linha por eixo,
 * com o vão entre os grupos dele — saiu em 19/11/2026 junto com os perfis: o
 * que ela media é desigualdade entre alunos, e isso o φ de Jain já publica
 * como número. */
export type CutChoice = CutAxis;

/** Os recortes na ordem do seletor, com o rótulo da tela. */
export const CUTS: { axis: CutChoice; label: string }[] = [
  { axis: "overall", label: "Geral" },
  { axis: "performance", label: "Desempenho" },
  { axis: "availability", label: "Disponibilidade" },
  { axis: "selectivity", label: "Seletividade" },
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

/** Os grupos de um recorte com a cor e o rótulo da tela. */
export function cutGroups(
  cut: CutAxis,
  config: CompareRequest,
  present: string[],
  palette: { solo: string }
): SeriesGroupStyle[] {
  if (cut === "overall") {
    return [{ key: "overall", label: "Geral", color: palette.solo }];
  }
  // As faixas vêm na ordem da API — da mais baixa para a mais alta —, e a
  // cor é da **posição**, não do nome: a rampa codifica essa ordem.
  const bands = Math.max(config.quantiles ?? present.length, present.length, 1);
  return present.map((key, index) => ({
    key,
    label: key,
    color: bandColor(index, bands),
  }));
}
