import { useMemo, useState } from "react";
import {
  AllocationTimeChart,
  Histogram,
  LineSample,
  SeriesChart,
  categoricalColors,
  formatCount,
  formatRatio,
  inkFor,
  soloColor,
  usePrefersDark,
} from "./charts";
import type {
  AllocationTimeLine,
  SeriesArmStyle,
  SeriesGroupStyle,
  SeriesLine,
} from "./charts";
import { BoxPlot } from "./charts";
import {
  AGGREGATE,
  CUTS,
  RULERS,
  cutDomain,
  cutGroups,
  pointsOf,
  rulerOf,
  seriesOf,
} from "./bands";
import type { CutChoice, RulerChoice } from "./bands";
import { boxStats } from "./equations";
import { describeComparison, formatRunDate, ComparisonRun } from "./history";
import { Trace } from "./Trace";
import { COMPARISON_ARMS } from "./types";
import { MAX_CUTS, readBandColors, writeBandColor } from "./profileColors";
import type { ClassCut, CompareRequest, Ruler, RunSummary } from "./types";

/** Períodos com uma casa: o tempo de formatura anda em frações de período, e duas casas sugeririam uma precisão que a amostra não tem */
const formatPeriods = (value: number) =>
  value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Uma grandeza comparada entre os modelos */
interface Metric {
  id: string;
  title: string;
  short: string;
  of: (run: RunSummary) => number | null;
  band?: string;
   /** Limites naturais da grandeza; o domínio é folgado em torno dos dados mas nunca passa daqui */
  bounds?: [number, number];
   /** De que lado está o melhor resultado — é o que decide o sinal de "seeds a favor" */
  betterWhen: "higher" | "lower" | null;
  format: (value: number) => string;
  zeroLine?: boolean;
}

/** A economia de créditos — **exclusiva do leilão** */
const CREDIT_METRICS: Metric[] = [
  {
    id: "credits_supply",
    title: "Orçamento de créditos por aluno",
    short: "Orçamento",
    of: () => null,
    band: "credits_supply",
    bounds: [0, Infinity],
    betterWhen: null,
    format: formatCount,
  },
  {
    id: "credits_spent",
    title: "Créditos gastos por aluno",
    short: "Gastos",
    of: () => null,
    band: "credits_spent",
    bounds: [0, Infinity],
    betterWhen: null,
    format: formatCount,
  },
  {
    id: "credits_returned",
    title: "Créditos retornados por aluno",
    short: "Retornados",
    of: () => null,
    band: "credits_returned",
    bounds: [0, Infinity],
    betterWhen: null,
    format: formatCount,
  },
];

/** Os recortes do gráfico de preço */
const CLASS_CUTS: { axis: ClassCut; label: string }[] = [
  { axis: "classes", label: "Turmas" },
  { axis: "hours", label: "Carga horária" },
  { axis: "curriculum_period", label: "Período" },
];

/** O rótulo em português de um grupo da oferta */
const classGroupLabel = (axis: ClassCut, key: string): string => {
  if (key === "elective") return "optativa";
  const value = Number(key);
  const number = Number.isFinite(value) ? value.toLocaleString("pt-BR") : key;
  switch (axis) {
    case "classes":
      return value === 1 ? "1 turma" : `${number} turmas`;
    case "hours":
      return `${number} h`;
    case "curriculum_period":
      return `${number}º período`;
  }
};

/** As métricas de alocação — as que avaliam a qualidade do que foi alocado */
const METRICS: Metric[] = [
  {
    id: "efficiency",
    title: "Satisfação (ψ̄)",
    short: "Satisfação (ψ̄)",
    of: (run) => run.efficiency,
    band: "efficiency",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "attendance",
    title: "Aproveitamento (θ)",
    short: "Aproveitamento (θ)",
    of: (run) => run.attendance ?? 0,
    band: "attendance",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "progress",
    title: "Progresso",
    short: "Progresso",
    of: (run) => run.progress,
    band: "progress",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "fidelity",
    title: "Fidelidade da mensagem",
    short: "Fidelidade",
    of: (run) => run.fidelity,
    band: "fidelity",
    bounds: [0, 1],
    betterWhen: null,
    format: formatRatio,
  },
  {
    id: "fairness",
    title: "Equidade (índice de Jain, φ)",
    short: "Equidade (φ)",
    of: (run) => run.fairness,
    band: "fairness",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "exclusion_rate",
    title: "Desperdício de vaga",
    short: "Desperdício",
    of: (run) => run.exclusion_rate,
    band: "exclusion_rate",
    bounds: [0, 1],
    betterWhen: "lower",
    format: formatRatio,
  },
  {
    id: "mean_round",
    title: "Rodada média (r̄)",
    short: "Rodada média (r̄)",
    of: (run) => run.mean_round ?? 1,
    band: "mean_round",
    bounds: undefined,
    betterWhen: "lower",
    format: formatRatio,
  },
  {
    id: "grade_average",
    title: "CR médio (N̄)",
    short: "CR médio",
    of: (run) => run.grade_average,
    band: "grade_average",
    bounds: [0, 10],
    betterWhen: null,
    format: formatRatio,
  },
  {
    id: "graduation_rate",
    title: "Fração de concluintes",
    short: "Concluintes",
    of: (run) => (run.population ? run.graduates / run.population : null),
    band: "graduation_rate",
    betterWhen: "higher",
    bounds: [0, 1],
    format: formatRatio,
  },
  {
    id: "time_to_graduate",
    title: "Tempo de formatura (períodos)",
    short: "Tempo (períodos)",
    of: (run) => run.time_to_graduate,
    betterWhen: "lower",
    format: formatPeriods,
  },
];


/** As quatro frações do funil de uma solicitação — `equations.request_funnel` */
const FUNNEL = [
  { key: "requested_share", title: "Fração de solicitadas" },
  { key: "granted_share", title: "Fração de deferidas" },
  { key: "attended_share", title: "Fração de cursadas" },
  { key: "approved_share", title: "Fração de aprovadas" },
] as const;

const ORDINALS = ["1ª", "2ª", "3ª", "4ª", "5ª", "6ª", "7ª", "8ª", "9ª", "10ª"];

/** Uma métrica por rodada do cenário: as vagas obtidas por aluno naquela rodada */
const roundMetrics = (rounds: number): Metric[] =>
  Array.from({ length: rounds }, (_, index) => {
    const ordinal = ORDINALS[index] ?? `${index + 1}ª`;
    return {
      id: `round-${index}`,
      title: `Alocações por aluno (${ordinal} rodada)`,
      short: `Alocações (${ordinal} rodada)`,
      of: (run) => run.allocations_per_round?.[index] ?? null,
      band: `round_${index + 1}`,
      bounds: [0, Infinity],
      betterWhen: null,
      format: formatCount,
    };
  });

/** Os dois braços do leilão que isolam o acúmulo: eles diferem em **uma** coisa só — `credits_ilp` abre todo período em C_min e não tem retorno, `credits_return` carrega o saldo e o alimenta com o k do cenário */
const WITH_ACCUMULATION = "credits_return";
const WITHOUT_ACCUMULATION = "credits_ilp";

/** A linha de base, contra a qual as diferenças da tabela de resumo são medidas: a matrícula por CR com varredura, que é o mecanismo real das universidades brasileiras */
const BASELINE = "ranking_greedy";

/** A grade de correlações: duas grandezas **do aluno** contra três do resultado dele */
const CORRELATIONS: { key: string; title: string }[] = [
  {
    key: "cr_satisfaction",
    title: "CR × satisfação (λ)",
  },
  {
    key: "cr_occupancy",
    title: "CR × ocupação",
  },
  {
    key: "cr_dissipation",
    title: "CR × retenção",
  },
  {
    key: "selectivity_satisfaction",
    title: "Seletividade × satisfação",
  },
  {
    key: "selectivity_occupancy",
    title: "Seletividade × ocupação",
  },
  {
    key: "selectivity_dissipation",
    title: "Seletividade × retenção",
  },
];

/** Sinal explícito: numa coluna de diferenças, "+0,04" e "−0,04" se distinguem de relance e "0,04" não */
const formatDelta = (value: number, format: (v: number) => string) =>
  `${value > 0 ? "+" : value < 0 ? "−" : ""}${format(Math.abs(value))}`;

export function Comparison({
  run,
  onReuseConfig,
  onRecut,
  recutting,
}: {
  run: ComparisonRun;
  onReuseConfig: () => void;
   /** Roda de novo com outros cortes */
  onRecut: (cuts: Partial<CompareRequest>) => void;
  recutting: boolean;
}) {
  const dark = usePrefersDark();
  const result = run.result;
  const ink = inkFor(dark);
   /** As duas escolhas que governam todos os gráficos: a **régua** do eixo X (período, idade ou coorte) e o **recorte** das linhas (a universidade inteira ou um dos quatro eixos de perfil) */
  const [rulerChoice, setRuler] = useState<RulerChoice>("period");
  const [cutChoice, setCut] = useState<CutChoice>("overall");
   /** As cores escolhidas para as faixas, por eixo */
  const [bandColors, setBandColors] = useState(readBandColors);
   /** Os cortes em edição, por eixo */
  const [cutDraft, setCutDraft] = useState<Record<string, number[]>>({});
   /** O recorte da oferta no gráfico de preço */
  const [priceCutChoice, setPriceCut] = useState<ClassCut>("curriculum_period");

   /** Os dois leilões são escolha de quem configura a comparação */
  const hasBothAuctions = [WITH_ACCUMULATION, WITHOUT_ACCUMULATION].every((key) =>
    result.arms.some((arm) => arm.key === key)
  );


  const arms: SeriesArmStyle[] = useMemo(
    () =>
      COMPARISON_ARMS.filter((arm) => result.arms.some((a) => a.key === arm.key)).map(
        (arm) => ({ key: arm.key, label: arm.label, dash: arm.dash })
      ),
    [result.arms]
  );

   /** O custo de **rodar** cada mecanismo, rodada a rodada */
  const allocationTimes: AllocationTimeLine[] = useMemo(
    () =>
      arms
        .map((arm) => ({
          ...arm,
          seconds:
            result.arms.find((entry) => entry.key === arm.key)?.allocation_seconds ?? [],
        }))
        .filter((line) => line.seconds.length > 0),
    [arms, result.arms]
  );

   /** Os recortes da oferta que esta comparação traz */
  const priceCuts = CLASS_CUTS.filter((option) =>
    result.arms.some((arm) =>
      arm.class_prices?.some((cut) => cut.axis === option.axis && cut.groups.length)
    )
  );
  const priceCut: ClassCut =
    priceCuts.some((option) => option.axis === priceCutChoice)
      ? priceCutChoice
      : (priceCuts[0]?.axis ?? "curriculum_period");

   /** As cores do recorte da oferta */
  const priceGroups: SeriesGroupStyle[] = useMemo(() => {
    const present = [
      ...new Set(
        result.arms.flatMap(
          (arm) =>
            arm.class_prices
              ?.find((cut) => cut.axis === priceCut)
              ?.groups.map((group) => group.group) ?? []
        )
      ),
    ];
    const labels = present.map((key) => classGroupLabel(priceCut, key));
    const colors = categoricalColors(labels, dark);
    return present.map((key, index) => ({
      key,
      label: labels[index],
      color: colors[labels[index]],
    }));
  }, [result.arms, priceCut, dark]);

   /** As linhas do preço: um grupo da oferta sob um modelo */
  const priceLines: SeriesLine[] = arms.flatMap((arm) =>
    (
      result.arms
        .find((entry) => entry.key === arm.key)
        ?.class_prices?.find((cut) => cut.axis === priceCut)?.groups ?? []
    ).map((group) => ({
      arm: arm.key,
      group: group.group,
      points: pointsOf(group).flatMap((x, i) => {
        const band = group.values.mean_price?.[i];
        return band
          ? [{ x, q1: band[0], median: band[1], q3: band[2], n: group.n[i] }]
          : [];
      }),
    }))
  );

  const series = useMemo(
    () =>
      Object.fromEntries(
        arms.map((arm) => [
          arm.key,
          seriesOf(result.arms.find((a) => a.key === arm.key)),
        ])
      ),
    [arms, result.arms]
  );

   /** As réguas que esta comparação traz */
  const rulers = RULERS.filter((option) =>
    Object.values(series).some((axes) =>
      axes.some((a) => rulerOf(a) === option.ruler && a.groups.length)
    )
  );
   /** O que o eixo X está mostrando */
  const view: RulerChoice =
    rulerChoice === AGGREGATE || rulers.some((r) => r.ruler === rulerChoice)
      ? rulerChoice
      : (rulers[0]?.ruler ?? "period");
  const aggregated = view === AGGREGATE;
  const ruler: Ruler = aggregated ? (rulers[0]?.ruler ?? "period") : (view as Ruler);
  const scale = RULERS.find((option) => option.ruler === ruler) ?? RULERS[0];

  const rulerAxes = useMemo(
    () => Object.values(series).flat().filter((a) => rulerOf(a) === ruler),
    [series, ruler]
  );

   /** Os recortes que esta comparação traz **nesta régua** */
  const cuts = CUTS.filter((option) =>
    rulerAxes.some((a) => a.axis === option.axis && a.groups.length)
  );
  const cut: CutChoice = cuts.some((c) => c.axis === cutChoice)
    ? cutChoice
    : (cuts[0]?.axis ?? "overall");


   /** Os modelos que produziram **o recorte escolhido** — os que o gráfico de faixas desenha, e os únicos que entram na legenda dele */
  const axisArms: SeriesArmStyle[] = useMemo(
    () =>
      arms.filter(
        (arm) =>
          cut === "overall" ||
          (series[arm.key] ?? []).some(
            (a) => rulerOf(a) === ruler && a.axis === cut && a.groups.length
          )
      ),
    [arms, series, ruler, cut]
  );

   /** O eixo escolhido no catálogo de recortes, com domínio, passo e os cortes em vigor — os do rascunho, se houver, senão os da execução */
  const cutOption = CUTS.find((option) => option.axis === cut);
  const runCuts = cutOption?.field ? (run.config[cutOption.field] ?? []) : [];
  const cutValues = cutOption?.field
    ? (cutDraft[cutOption.field] ?? runCuts)
    : [];
  const [cutLow, cutHigh] = cutDomain(cut) ?? [
    0,
    Number.POSITIVE_INFINITY,
  ];
  const cutsValid =
    cutValues.every((value) => value > cutLow && value < cutHigh) &&
    new Set(cutValues).size === cutValues.length;
  const cutsChanged =
    cutValues.length !== runCuts.length ||
    [...cutValues]
      .sort((a, b) => a - b)
      .some((value, index) => value !== [...runCuts].sort((a, b) => a - b)[index]);
  const nextCut = (() => {
    const step = cutOption?.step ?? 1;
    const maior = cutValues.length ? Math.max(...cutValues) : cutLow;
    const teto = Number.isFinite(cutHigh) ? cutHigh : maior + 10 * step;
    return Math.round((maior + (teto - maior) / 2) / step) * step;
  })();

  const axisOf = (armKey: string) =>
    series[armKey]?.find((a) => rulerOf(a) === ruler && a.axis === cut);

  const groups = useMemo(() => {
    const present = [
      ...new Set(
        rulerAxes.flatMap(
          (axis) => (axis.axis === cut ? axis.groups.map((g) => g.group) : [])
        )
      ),
    ];
    return cutGroups(cut, present, {
      solo: soloColor(dark),
      bands: bandColors[cut],
    });
  }, [rulerAxes, cut, dark, bandColors]);

   /** A seção da economia só aparece com leilão na comparação **e** com dado dela: as gravadas antes de 14/11/2026 não a têm, e um gráfico vazio diria menos que seção nenhuma */
  const hasCredits = Object.values(series).some((axes) =>
    axes.some((axis) =>
      axis.groups.some((group) =>
        group.values.credits_supply?.some((band) => band !== null)
      )
    )
  );

  const linesOf = (key: string): SeriesLine[] =>
    arms.flatMap((arm) =>
          (axisOf(arm.key)?.groups ?? []).map((group) => ({
            arm: arm.key,
            group: group.group,
            points: pointsOf(group).flatMap((x, i) => {
              const band = group.values[key]?.[i];
              return band
                ? [{ x, q1: band[0], median: band[1], q3: band[2], n: group.n[i] }]
                : [];
            }),
          }))
        );

   /** As execuções de um braço, na ordem das seeds */
  const runsOf = (key: string): RunSummary[] =>
    result.arms.find((arm) => arm.key === key)?.runs ?? [];

   /** A cor de cada modelo no agregado */
  const armColors = useMemo(
    () => categoricalColors(arms.map((arm) => arm.label), dark),
    [arms, dark]
  );

   /** As duas distribuições de entrada do cenário */
  const scenarioHistograms = [
    result.grade_distribution?.length ? (
      <Histogram
        key="notas"
        title="Notas de primeira tentativa"
        fractions={result.grade_distribution}
        domain={[0, 10]}
      />
    ) : null,
    result.interest_distribution?.length ? (
      <Histogram
        key="interesse"
        title="Interesse"
        fractions={result.interest_distribution}
      />
    ) : null,
  ].filter(Boolean);

   /** Quantas rodadas o cenário teve, lido do próprio resultado */
  const rounds = useMemo(
    () =>
      Math.max(
        0,
        ...result.arms.flatMap((arm) =>
          arm.runs.map((entry) => entry.allocations_per_round?.length ?? 0)
        )
      ),
    [result.arms]
  );
  const saturation = useMemo(() => roundMetrics(rounds), [rounds]);

   /** Os valores de uma métrica numa amostra */
  const valuesOf = (key: string, metric: Metric): number[] =>
    runsOf(key)
      .map(metric.of)
      .filter((value): value is number => value !== null && value !== undefined);

   /** Comparação pareada entre dois braços: em quantas das N seeds o primeiro saiu melhor que o segundo */
  const paired = (metric: Metric, aKey: string, bKey: string) => {
    if (metric.betterWhen === null) return null;
    const a = runsOf(aKey);
    const b = runsOf(bKey);
    let favour = 0;
    let comparable = 0;
    a.forEach((left, i) => {
      const right = b[i];
      if (!right) return;
      const x = metric.of(left);
      const y = metric.of(right);
      if (x === null || y === null) return;
      comparable++;
      if (metric.betterWhen === "higher" ? x > y : x < y) favour++;
    });
    return { favour, comparable };
  };

   /** Quantas seeds o acúmulo fez *subir* — contagem descritiva, sem juízo de melhor ou pior, porque para λ e para a saturação não há um lado bom */
  const raisedByAccumulation = (metric: Metric) => {
    const a = runsOf(WITH_ACCUMULATION);
    const b = runsOf(WITHOUT_ACCUMULATION);
    let up = 0;
    let comparable = 0;
    a.forEach((left, i) => {
      const right = b[i];
      if (!right) return;
      const x = metric.of(left);
      const y = metric.of(right);
      if (x === null || y === null) return;
      comparable++;
      if (x > y) up++;
    });
    return { up, comparable };
  };

  const medianOf = (key: string, metric: Metric) =>
    boxStats(valuesOf(key, metric))?.median ?? null;

   /** Uma linha por braço na tabela de resumo — só os que rodaram, porque uma linha inteira em traços não diz nada sobre o modelo que ficou de fora */
  const summaryRows = (metric: Metric) =>
    COMPARISON_ARMS.filter((arm) =>
      result.arms.some((entry) => entry.key === arm.key)
    ).map((arm, index) => {
      const box = boxStats(valuesOf(arm.key, metric));
      const baseline = medianOf(BASELINE, metric);
      const pairing = arm.key === BASELINE ? null : paired(metric, arm.key, BASELINE);
      return (
        <tr key={`${metric.id}-${arm.key}`}>
          {/* O nome da métrica só na primeira linha do bloco: repetido ele
              viraria ruído entre números que se comparam. */}
          <td>{index === 0 ? metric.short : ""}</td>
          <td>
            <LineSample dash={arm.dash} color={ink.secondary} /> {arm.label}
          </td>
          <td>{box ? metric.format(box.min) : "—"}</td>
          <td>{box ? metric.format(box.q1) : "—"}</td>
          <td>{box ? metric.format(box.median) : "—"}</td>
          <td>{box ? metric.format(box.q3) : "—"}</td>
          <td>{box ? metric.format(box.max) : "—"}</td>
          <td>
            {arm.key === BASELINE || box === null || baseline === null
              ? ""
              : metric.betterWhen === null
                ? "—"
                : formatDelta(box.median - baseline, metric.format)}
          </td>
          <td>
            {arm.key === BASELINE
              ? ""
              : pairing
                ? `${pairing.favour}/${pairing.comparable}`
                : "—"}
          </td>
        </tr>
      );
    });

  const accumulationRow = (metric: Metric) => {
    const flat = medianOf(WITHOUT_ACCUMULATION, metric);
    const accumulated = medianOf(WITH_ACCUMULATION, metric);
    const baseline = medianOf(BASELINE, metric);
    const { up, comparable } = raisedByAccumulation(metric);
    return (
      <tr key={metric.id}>
        <td>{metric.short}</td>
        <td>{flat === null ? "—" : metric.format(flat)}</td>
        <td>{accumulated === null ? "—" : metric.format(accumulated)}</td>
        <td>
          {flat === null || accumulated === null
            ? "—"
            : formatDelta(accumulated - flat, metric.format)}
        </td>
        <td>{`${up}/${comparable}`}</td>
        <td className="muted-cell">{baseline === null ? "—" : metric.format(baseline)}</td>
      </tr>
    );
  };

  const chart = (
    id: string,
    title: string,
    key: string,
    extra: {
      bounds?: [number, number];
      format?: (value: number) => string;
      zeroLine?: boolean;
      accent?: string;
    } = {}
  ) => (
    <SeriesChart
      key={id}
      title={title}
      lines={linesOf(key)}
      groups={groups}
      arms={axisArms}
      runs={result.runs}
      xLabel={scale.point}
      {...extra}
    />
  );

   /** Uma caixa por modelo, sobre as seeds */
  const metricBox = (metric: Metric) => (
    <BoxPlot
      key={metric.id}
      title={metric.title}
      bounds={metric.bounds ?? [0, 1]}
      format={metric.format ?? formatRatio}
      rows={arms.map((arm) => ({
        key: arm.key,
        label: arm.label,
        color: armColors[arm.label] ?? soloColor(dark),
        values: runsOf(arm.key)
          .map((entry) => metric.of(entry))
          .filter((value): value is number => typeof value === "number"),
      }))}
    />
  );

  const metricChart = (metric: Metric) =>
    aggregated
      ? metricBox(metric)
      : metric.band
        ? chart(metric.id, metric.title, metric.band, {
            bounds: metric.bounds,
            format: metric.format,
            zeroLine: metric.zeroLine,
          })
        : null;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Comparação de {formatRunDate(run.at)}</h1>
          <p className="note">{describeComparison(run)}</p>
        </div>
        <button className="secondary" onClick={onReuseConfig}>
          Reabrir esta configuração
        </button>
      </div>

      <div className="panel panel-switch">
        <h2>
          {result.runs} simulações de cada modelo — {result.runs * result.arms.length}{" "}
          simulações
        </h2>
        <div className="switch-set">
          {(rulers.length > 1 || true) && (
            <div className="switch-group" role="group" aria-label="Eixo">
              <span>Eixo</span>
              <div className="view-switch">
                {[
                  ...rulers.map((option) => ({
                    key: option.ruler as RulerChoice,
                    label: option.label,
                  })),
                  { key: AGGREGATE as RulerChoice, label: "Agregado" },
                ].map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    className={view === option.key ? "on" : ""}
                    aria-pressed={view === option.key}
                    onClick={() => setRuler(option.key)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          )}
          {cuts.length > 1 && (
            <div className="switch-group" role="group" aria-label="Linhas">
              <span>Linhas</span>
              <select
                value={cut}
                onChange={(e) => setCut(e.target.value as CutChoice)}
              >
                {cuts.map((option) => (
                  <option key={option.axis} value={option.axis}>
                    {option.label}
                  </option>
                ))}
              </select>
              {/* Os cortes do eixo escolhido. Um corte a mais é uma faixa a
                  mais. Eles são do **motor**, não da tela — ver `onRecut` —,
                  então a edição fica em rascunho e o Aplicar roda de novo; a
                  cada tecla custaria N simulações por braço. */}
              {cutOption?.field && (
                <div className="cut-list">
                  {cutValues
                    .map((cut, index) => [cut, index] as const)
                    .sort((a, b) => b[0] - a[0])
                    .map(([cut, index]) => (
                      <input
                        key={index}
                        type="number"
                        min={cutLow}
                        max={Number.isFinite(cutHigh) ? cutHigh : undefined}
                        step={cutOption.step ?? 1}
                        value={cut.toFixed(cutOption.decimals ?? 0)}
                        onChange={(e) => {
                          const next = [...cutValues];
                          next[index] = Number(e.target.value);
                          setCutDraft({ ...cutDraft, [cutOption.field!]: next });
                        }}
                      />
                    ))}
                  <button
                    type="button"
                    className="ghost"
                    disabled={cutValues.length >= MAX_CUTS}
                    onClick={() =>
                      setCutDraft({
                        ...cutDraft,
                        [cutOption.field!]: [...cutValues, nextCut],
                      })
                    }
                  >
                    +
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={!cutValues.length}
                    onClick={() =>
                      setCutDraft({
                        ...cutDraft,
                        [cutOption.field!]: cutValues
                          .slice()
                          .sort((a, b) => a - b)
                          .slice(0, -1),
                      })
                    }
                  >
                    −
                  </button>
                  {cutsChanged && (
                    <button
                      type="button"
                      className="ghost"
                      disabled={recutting || !cutsValid}
                      onClick={() =>
                        onRecut({
                          [cutOption.field!]: [...cutValues].sort((a, b) => a - b),
                        } as Partial<CompareRequest>)
                      }
                    >
                      {recutting ? "Rodando…" : "Aplicar"}
                    </button>
                  )}
                  {!cutsValid && (
                    <span className="field-error">
                      entre {cutLow.toLocaleString("pt-BR")} e{" "}
                      {Number.isFinite(cutHigh)
                        ? cutHigh.toLocaleString("pt-BR")
                        : "∞"}
                      , sem repetir
                    </span>
                  )}
                </div>
              )}
              {/* Uma cor por faixa, da mais baixa para a mais alta — a mesma
                  ordem em que a API as lista. Vazia cai na rampa padrão, de
                  modo que pintar uma faixa não repinte as outras. */}
              {cut !== "overall" && groups.length > 1 && (
                <div className="band-colors">
                  {groups.map((group, index) => (
                    <label key={group.key} title={group.label}>
                      <input
                        type="color"
                        value={group.color}
                        onChange={(e) =>
                          setBandColors(
                            writeBandColor(cut, index, e.target.value)
                          )
                        }
                      />
                      <span>{group.label}</span>
                    </label>
                  ))}
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => {
                      let next = bandColors;
                      groups.forEach((_, index) => {
                        next = writeBandColor(cut, index, null);
                      });
                      setBandColors(next);
                    }}
                  >
                    Padrão
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <section className="chart-section">
        <header className="chart-section-head">
          <h2>Métricas de alocação</h2>
          <p>
            A mediana entre as simulações em cada ponto do eixo, com o
            intervalo interquartil em faixa. O tempo de formatura não entra: é
            da simulação inteira, não de um ponto dela.
          </p>
        </header>
        <div className="chart-grid">
          {METRICS.map(metricChart)}
          {/* O peso de cada ponto, no fim da grade — e o **teste de validade
              da janela**: em regime ele é plano, porque entra uma coorte e sai
              outra. Se subir ao longo da janela, a pré-população foi curta e
              o que as curvas mostram é a rampa, não o mecanismo.

              Num eixo de estado este é o gráfico de **alunos ativos por
              faixa**, e o rótulo muda para dizê-lo: ali o calouro fica fora da
              faixa (CR 0 é ausência de medida, não medida de 0), então medido
              e ativo são o mesmo conjunto. No "Geral" não são — o calouro
              conta como ativo e sai das médias —, e o rótulo da régua continua
              sendo o certo. */}
          {chart(
            "students",
            cut === "overall" ? scale.weight : "Alunos ativos na faixa",
            "students",
            {
              bounds: [0, Infinity],
              format: formatCount,
            }
          )}
        </div>
      </section>

      {rounds > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>Saturação da demanda</h2>
            <p>
              A mesma rodada ao longo do horizonte — a 1ª rodada de cada
              período, a 2ª de cada período —, para o decaimento se ler junto
              com o momento em que acontece.
            </p>
          </header>
          <div className="chart-grid">{saturation.map(metricChart)}</div>
        </section>
      )}

      <section className="chart-section">
        <header className="chart-section-head">
          <h2>Correlações</h2>
          <p>
            O que anda junto com o quê: duas grandezas do aluno — o CR e a
            seletividade — contra três do resultado dele. Descrevem, não
            pontuam: qual lado é melhor depende de alocar por mérito passado
            ou por necessidade, e essa é escolha de quem lê.
          </p>
        </header>
        <div className="chart-grid">
          {CORRELATIONS.map((cell) =>
            chart(cell.key, cell.title, cell.key, {
              bounds: [-1, 1],
              format: formatRatio,
              zeroLine: true,
            })
          )}
        </div>
      </section>

      <section className="chart-section">
        <header className="chart-section-head">
          <h2>Solicitações de disciplinas</h2>
          <p>
            O funil de cada disciplina que ainda falta ao aluno, fração a
            fração: quanto ele pediu do que lhe faltava, quanto do que pediu
            lhe foi deferido, quanto do que levou chegou a cursar e quanto do
            que cursou aprovou. Cada uma divide pelo nó anterior, de modo que
            as quatro vão de 0 a 1 e cada painel se mexe só quando o nó dele
            se mexe.
          </p>
        </header>
        <div className="chart-grid">
          {FUNNEL.map((share) =>
            chart(share.key, share.title, share.key, {
              bounds: [0, 1],
              format: formatRatio,
            })
          )}
        </div>
      </section>

      {scenarioHistograms.length > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>As distribuições do cenário</h2>
          </header>
          <div className="chart-grid">{scenarioHistograms}</div>
        </section>
      )}

      {allocationTimes.length > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>O custo de rodar o mecanismo</h2>
          </header>
          <div className="chart-grid">
            <AllocationTimeChart
              title="Tempo de alocação por rodada (escala log)"
              lines={allocationTimes}
            />
          </div>
        </section>
      )}

      {hasCredits && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>Economia de créditos</h2>
          </header>
          <div className="chart-grid">{CREDIT_METRICS.map(metricChart)}</div>

          {priceCuts.length > 0 && (
            <>
              {priceCuts.length > 1 && (
                <div className="switch-group" role="group" aria-label="Linhas do preço">
                  <span>Linhas</span>
                  <div className="view-switch">
                    {priceCuts.map((option) => (
                      <button
                        key={option.axis}
                        type="button"
                        className={priceCut === option.axis ? "on" : ""}
                        aria-pressed={priceCut === option.axis}
                        onClick={() => setPriceCut(option.axis)}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="chart-grid">
                <SeriesChart
                  title="Preço das disciplinas"
                  lines={priceLines}
                  groups={priceGroups}
                  arms={arms}
                  runs={result.runs}
                  xLabel={RULERS[0].point}
                  bounds={[0, Infinity]}
                  format={formatCount}
                />
              </div>
            </>
          )}
        </section>
      )}

      {hasBothAuctions && (
      <div className="panel">
        <h2>O que o acúmulo de créditos muda</h2>
        <table>
          <thead>
            <tr>
              <th>Métrica</th>
              <th>Igualitário</th>
              <th>Com PLI</th>
              <th>Efeito do acúmulo</th>
              <th>Subiu em</th>
              <th>CR (referência)</th>
            </tr>
          </thead>
          <tbody>{[...METRICS, ...saturation].map(accumulationRow)}</tbody>
        </table>
      </div>
      )}

      <div className="panel">
        <h2>Resumo das distribuições</h2>
        <table>
          <thead>
            <tr>
              <th>Métrica</th>
              <th>Modelo</th>
              <th>Mín</th>
              <th>1º quartil</th>
              <th>Mediana</th>
              <th>3º quartil</th>
              <th>Máx</th>
              <th>Diferença</th>
              <th>Seeds a favor</th>
            </tr>
          </thead>
          <tbody>{[...METRICS, ...saturation].flatMap(summaryRows)}</tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Simulação a simulação</h2>
        <table>
          <thead>
            <tr>
              <th>Seed</th>
              <th>Períodos</th>
              <th>Formados</th>
              {METRICS.map((metric) => (
                <th key={metric.id}>{metric.short}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: result.runs }, (_, i) => {
              const row = arms.map((arm) => runsOf(arm.key)[i]).filter(Boolean);
              if (!row.length) return null;
              const join = (
                of: (run: RunSummary) => number | null,
                format: (value: number) => string
              ) =>
                row
                  .map((entry) => {
                    const value = of(entry);
                    return value === null ? "—" : format(value);
                  })
                  .join(" / ");
              const periods = [...new Set(row.map((entry) => entry.periods))];
              return (
                <tr key={row[0].seed}>
                  <td>{row[0].seed}</td>
                  <td>{periods.length === 1 ? periods[0] : periods.join(" / ")}</td>
                  <td>{join((entry) => entry.graduates, formatCount)}</td>
                  {METRICS.map((metric) => (
                    <td key={metric.id}>{join(metric.of, metric.format)}</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Por último, o caso individual. Tudo acima é agregado — a distribuição
          entre as simulações e o perfil dentro delas —, e esta seção é a porta
          de saída para o outro extremo: um aluno, uma disciplina, uma rodada.
          Fica no fim porque custa uma simulação a mais, e porque a pergunta
          que ela responde ("por que este número saiu assim?") só aparece
          depois de ver o número. */}
      <Trace run={run} />
    </div>
  );
}
