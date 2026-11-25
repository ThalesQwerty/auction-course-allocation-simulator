import { useMemo, useState } from "react";
import {
  LineSample,
  SeriesChart,
  categoricalColors,
  formatCount,
  formatRatio,
  inkFor,
  soloColor,
  usePrefersDark,
} from "./charts";
import type { SeriesArmStyle, SeriesLine } from "./charts";
import { BoxPlot } from "./charts";
import {
  CUTS,
  PERIOD_POINT,
  SCATTER_AXES,
  cutDomain,
  cutGroups,
  pointsOf,
  seriesOf,
  validCuts,
} from "./bands";
import type { AxisChoice, CutChoice } from "./bands";
import { cutBands } from "./cutBands";
import { studentCurves } from "./studentCurves";
import { boxStats } from "./equations";
import { describeComparison, formatRunDate, ComparisonRun } from "./history";
import { Trace } from "./Trace";
import { COMPARISON_ARMS } from "./types";
import { MAX_CUTS, readBandColors, writeBandColor } from "./profileColors";
import type { RunSummary, StudentPoint } from "./types";

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
   /** A grandeza de vida inteira do aluno, quando ela existe: sem ela a métrica não vai à dispersão */
  point?: (student: StudentPoint) => number | null;
   /** As que não se partem em faixas — a equidade é do conjunto, não do aluno */
  soloOnly?: boolean;
}

/** Os recortes do gráfico de preço */
/** As métricas de alocação — as que avaliam a qualidade do que foi alocado */
/** Quantos pontos a curva por aluno tem por padrão, e o teto que a tela aceita */
const DEFAULT_CURVE_POINTS = 40;

const MAX_CURVE_POINTS = 300;

const CURVE_POINT_STEP = 10;

const METRICS: Metric[] = [
  {
    id: "satisfaction",
    title: "Satisfação (ψ̄)",
    short: "Satisfação (ψ̄)",
    of: (run) => run.satisfaction,
    point: (student) => student.satisfaction,
    band: "satisfaction",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "attendance",
    title: "Aproveitamento (θ)",
    short: "Aproveitamento (θ)",
    of: (run) => run.attendance ?? 0,
    point: (student) => student.attendance,
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
    point: (student) => student.progress,
    band: "progress",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "fairness",
    title: "Equidade (índice de Jain, φ)",
    short: "Equidade (φ)",
    of: (run) => run.fairness,
    soloOnly: true,
    band: "fairness",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "mean_round",
    title: "Rodada média (r̄)",
    short: "Rodada média (r̄)",
    of: (run) => run.mean_round ?? 1,
    point: (student) => student.mean_round,
    band: "mean_round",
    bounds: undefined,
    betterWhen: "lower",
    format: formatRatio,
  },
];

/** O que se publica **ao lado** das métricas: quem sobreviveu à coorte e até onde chegou. Não são métricas de alocação, e por isso ficam fora da dispersão e do recorte em faixas */
const CONTEXT: Metric[] = [
  {
    id: "graduation_rate",
    title: "Fração de concluintes",
    short: "Concluintes",
    of: (run) => (run.population ? run.graduates / run.population : null),
    band: "graduation_rate",
    soloOnly: true,
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


/** Os dois braços do leilão que isolam o acúmulo: eles diferem em **uma** coisa só — `credits_ilp` abre todo período em C_min e não tem retorno, `credits_return` carrega o saldo e o alimenta com o k do cenário */
const WITH_ACCUMULATION = "credits_return";
const WITHOUT_ACCUMULATION = "credits_ilp";

/** A linha de base, contra a qual as diferenças da tabela de resumo são medidas: a matrícula por CR com varredura, que é o mecanismo real das universidades brasileiras */
const BASELINE = "ranking_greedy";

/** Sinal explícito: numa coluna de diferenças, "+0,04" e "−0,04" se distinguem de relance e "0,04" não */
const formatDelta = (value: number, format: (v: number) => string) =>
  `${value > 0 ? "+" : value < 0 ? "−" : ""}${format(Math.abs(value))}`;

export function Comparison({
  run,
  onReuseConfig,
}: {
  run: ComparisonRun;
  onReuseConfig: () => void;
}) {
  const dark = usePrefersDark();
  const result = run.result;
  const ink = inkFor(dark);
   /** As duas escolhas que governam todos os gráficos: a **régua** do eixo X (período, idade ou coorte) e o **recorte** das linhas (a universidade inteira ou um dos quatro eixos de perfil) */
  const [axisChoice, setAxis] = useState<AxisChoice>("period");
  const [cutChoice, setCut] = useState<CutChoice>("overall");
   /** As cores escolhidas para as faixas, por eixo */
  const [bandColors, setBandColors] = useState(readBandColors);
   /** Quantos pontos a curva por aluno tem: cada um é uma faixa de quantil da coorte */
  const [curvePoints, setCurvePoints] = useState(DEFAULT_CURVE_POINTS);
   /** Os cortes de cada eixo: escolha de **visualização**, porque o recorte sai das linhas cruas. `applied` guarda o último conjunto válido, para o gráfico não piscar enquanto se digita */
  const [cutState, setCutState] = useState(() => {
    const start: Record<string, number[]> = {
      grade_average: [...(run.config.grade_cuts ?? [])],
      reserve: [...(run.config.reserve_cuts ?? [])],
    };
    return { typed: start, applied: start };
  });

  const changeCuts = (axis: CutChoice, values: number[]) =>
    setCutState((current) => {
      const typed = { ...current.typed, [axis]: values };
      return {
        typed,
        applied: validCuts(axis, values) ? typed : current.applied,
      };
    });
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

  const series = useMemo(
    () =>
      Object.fromEntries(
        arms.map((arm) => {
          const found = result.arms.find((a) => a.key === arm.key);
          const stored = seriesOf(found);
          const live = (["grade_average", "reserve"] as const).flatMap((axis) => {
            const option = CUTS.find((entry) => entry.axis === axis);
            const bands =
              found && option?.domain
                ? cutBands(
                    found.runs,
                    axis,
                    cutState.applied[axis] ?? [],
                    option.domain,
                    option.decimals ?? 0
                  )
                : null;
            return bands ? [bands] : [];
          });
          // Sem linhas cruas (execução antiga) só resta o recorte que o motor gravou
          return [
            arm.key,
            live.length
              ? [...stored.filter((axis) => axis.axis === "overall"), ...live]
              : stored,
          ];
        })
      ),
    [arms, result.arms, cutState.applied]
  );

   /** O recorte é editável quando sai das linhas cruas; execução antiga trouxe faixas fixas */
  const editableCuts = result.arms.some((arm) =>
    arm.runs.some((entry) => entry.observations?.period.length)
  );

   /** Quanto dos períodos medidos bateu no teto de rodadas: é onde r̄ perde a cauda */
  const cappedShare = useMemo(() => {
    const todos = result.arms.flatMap((arm) => arm.runs);
    const total = todos.reduce((soma, run) => soma + run.periods, 0);
    const teto = todos.reduce((soma, run) => soma + (run.capped_periods ?? 0), 0);
    return total > 0 ? teto / total : null;
  }, [result.arms]);

   /** Um ponto por aluno medido, braço a braço */
  const pointsOfArm = (key: string): StudentPoint[] =>
    result.arms.find((arm) => arm.key === key)?.points ?? [];

   /** A dispersão só existe com ponto gravado: as comparações antigas não têm */
  const hasPoints = result.arms.some((arm) => (arm.points?.length ?? 0) > 0);

   /** O que o eixo X está mostrando */
  const view: AxisChoice =
    !hasPoints && (axisChoice === "grade_average" || axisChoice === "reserve")
      ? "period"
      : axisChoice;
  const aggregated = view === "aggregate";
  const scattered = view === "grade_average" || view === "reserve";
  const scatterAxis = SCATTER_AXES.find((option) => option.key === view);

  const rulerAxes = useMemo(() => Object.values(series).flat(), [series]);

   /** Os recortes que esta comparação traz */
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
            (a) => a.axis === cut && a.groups.length
          )
      ),
    [arms, series, cut]
  );

   /** O eixo escolhido no catálogo de recortes, com domínio, passo e os cortes em vigor — os do rascunho, se houver, senão os da execução */
  const cutOption = CUTS.find((option) => option.axis === cut);
  const cutValues = cutOption?.field ? (cutState.typed[cut] ?? []) : [];
  const [cutLow, cutHigh] = cutDomain(cut) ?? [
    0,
    Number.POSITIVE_INFINITY,
  ];
  const cutsValid = validCuts(cut, cutValues);
  const nextCut = (() => {
    const step = cutOption?.step ?? 1;
    const maior = cutValues.length ? Math.max(...cutValues) : cutLow;
    const teto = Number.isFinite(cutHigh) ? cutHigh : maior + 10 * step;
    return Math.round((maior + (teto - maior) / 2) / step) * step;
  })();

  const axisOf = (armKey: string, axis: CutChoice = cut) =>
    series[armKey]?.find((a) => a.axis === axis);

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

   /** O recorte "Geral" — o que as métricas que não se partem em faixas usam */
  const soloGroups = useMemo(
    () => cutGroups("overall", [], { solo: soloColor(dark) }),
    [dark]
  );

  const linesOf = (key: string, axis: CutChoice = cut): SeriesLine[] =>
    arms.flatMap((arm) =>
          (axisOf(arm.key, axis)?.groups ?? []).map((group) => ({
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
      solo?: boolean;
    } = {}
  ) => {
    const { solo, ...rest } = extra;
    const axis: CutChoice = solo ? "overall" : cut;
    return (
      <SeriesChart
        key={id}
        title={title}
        lines={linesOf(key, axis)}
        groups={solo ? soloGroups : groups}
        arms={solo ? arms : axisArms}
        runs={result.runs}
        xLabel={PERIOD_POINT}
        {...rest}
      />
    );
  };

   /** A métrica sobre a grandeza de vida inteira escolhida: um ponto por faixa de quantil da coorte */
  const metricCurve = (metric: Metric) => {
    if (!scatterAxis || !metric.point) return null;
    const curves = studentCurves(
      arms.map((arm) => ({ key: arm.key, points: pointsOfArm(arm.key) })),
      scatterAxis.of,
      metric.point,
      curvePoints
    );
    const lines: SeriesLine[] = arms.flatMap((arm) =>
      curves[arm.key]?.length
        ? [{ group: "overall", arm: arm.key, points: curves[arm.key] }]
        : []
    );
    if (!lines.length) return null;
    return (
      <SeriesChart
        key={metric.id}
        title={metric.title}
        lines={lines}
        groups={soloGroups}
        arms={arms}
        runs={result.runs}
        bounds={metric.bounds}
        format={metric.format}
        xLabel={(x) => `${scatterAxis.label} ${scatterAxis.format(x)}`}
        axisLabel={scatterAxis.label}
        showCount
        foot="mediana · intervalo interquartil entre os alunos da faixa"
      />
    );
  };

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

  const metricChart = (metric: Metric) => {
    if (scattered) return metricCurve(metric);
    if (aggregated) return metricBox(metric);
    if (!metric.band) return null;
    return chart(metric.id, metric.title, metric.band, {
      bounds: metric.bounds,
      format: metric.format,
      zeroLine: metric.zeroLine,
      solo: metric.soloOnly,
    });
  };

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
          <div className="switch-group" role="group" aria-label="Eixo">
            <span>Eixo</span>
            <div className="view-switch">
              {[
                { key: "period" as AxisChoice, label: "Período" },
                ...(hasPoints
                  ? SCATTER_AXES.map((option) => ({
                      key: option.key as AxisChoice,
                      label: option.label,
                    }))
                  : []),
                { key: "aggregate" as AxisChoice, label: "Agregado" },
              ].map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className={view === option.key ? "on" : ""}
                  aria-pressed={view === option.key}
                  onClick={() => setAxis(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
          {scattered && (
            <div className="switch-group">
              <span>Pontos</span>
              <input
                type="number"
                min={CURVE_POINT_STEP}
                max={MAX_CURVE_POINTS}
                step={CURVE_POINT_STEP}
                value={curvePoints}
                onChange={(e) => {
                  const asked = Number(e.target.value);
                  if (Number.isFinite(asked)) setCurvePoints(asked);
                }}
              />
            </div>
          )}
          {!scattered && cuts.length > 1 && (
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
              {/* Os cortes do eixo escolhido: um corte a mais é uma faixa a
                  mais. Saem das linhas cruas, então valem na hora. */}
              {cutOption?.field && editableCuts && (
                <div className="cut-list">
                  {cutValues
                    .map((value, index) => [value, index] as const)
                    .sort((a, b) => b[0] - a[0])
                    .map(([value, index]) => (
                      <input
                        key={index}
                        type="number"
                        min={cutLow}
                        max={Number.isFinite(cutHigh) ? cutHigh : undefined}
                        step={cutOption.step ?? 1}
                        value={value.toFixed(cutOption.decimals ?? 0)}
                        onChange={(e) => {
                          const next = [...cutValues];
                          next[index] = Number(e.target.value);
                          changeCuts(cut, next);
                        }}
                      />
                    ))}
                  <button
                    type="button"
                    className="ghost"
                    disabled={cutValues.length >= MAX_CUTS}
                    onClick={() => changeCuts(cut, [...cutValues, nextCut])}
                  >
                    +
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={!cutValues.length}
                    onClick={() =>
                      changeCuts(
                        cut,
                        cutValues.slice().sort((a, b) => a - b).slice(0, -1)
                      )
                    }
                  >
                    −
                  </button>
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
            {scattered
              ? "Um ponto por aluno medido, com a média dos períodos dele. A equidade não entra: é do conjunto, não do aluno."
              : "A mediana entre as simulações em cada ponto do eixo, com o intervalo interquartil em faixa."}
          </p>
          {cappedShare !== null && (
            <p className="note">
              {formatRatio(cappedShare)} dos períodos usaram todas as rodadas do
              cenário, e neles r̄ sai censurada para baixo.
            </p>
          )}
        </header>
        <div className="chart-grid">
          {METRICS.map(metricChart)}
        </div>
      </section>

      <section className="chart-section">
        <header className="chart-section-head">
          <h2>A coorte medida</h2>
          <p>
            A série acima encolhe conforme a coorte sai, por conclusão ou
            jubilamento, e por isso se lê ao lado destes dois.
          </p>
        </header>
        <div className="chart-grid">
          {CONTEXT.map((metric) =>
            aggregated
              ? metricBox(metric)
              : metric.band
                ? chart(metric.id, metric.title, metric.band, {
                    bounds: metric.bounds,
                    format: metric.format,
                    solo: true,
                  })
                : null
          )}
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
          {!aggregated &&
            chart("students", "Alunos medidos", "students", {
              bounds: [0, Infinity],
              format: formatCount,
              solo: true,
            })}
        </div>
      </section>

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
          <tbody>{[...METRICS, ...CONTEXT].map(accumulationRow)}</tbody>
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
          <tbody>{[...METRICS, ...CONTEXT].flatMap(summaryRows)}</tbody>
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
