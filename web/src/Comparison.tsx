import { useEffect, useMemo, useState } from "react";
import {
  SeriesChart,
  formatCount,
  formatRatio,
  soloColor,
  usePrefersDark,
} from "./charts";
import type { SeriesArmStyle, SeriesLine } from "./charts";
import {
  CUTS,
  PERIOD_POINT,
  SCATTER_AXES,
  cutDomain,
  cutGroups,
  validCuts,
} from "./bands";
import type { AxisChoice, CutChoice } from "./bands";
import { comparisonCurve, comparisonSeries } from "./api";
import { describeComparison, formatRunDate, ComparisonRun } from "./history";
import { RunProgress, RunProgressCard } from "./RunProgress";
import { Trace } from "./Trace";
import { COMPARISON_ARMS } from "./types";
import {
  MAX_CUTS,
  bandColor,
  readBandColors,
  writeBandColor,
} from "./profileColors";
import type { CurvePayload, SeriesPayload } from "./types";

/** Uma grandeza comparada entre os modelos */
interface Metric {
  id: string;
  title: string;
  short: string;
   /** A coluna com que a API nomeia esta grandeza */
  band?: string;
   /** Limites naturais da grandeza; o domínio é folgado em torno dos dados mas nunca passa daqui */
  bounds?: [number, number];
   /** De que lado está o melhor resultado — é o que decide o sinal de "seeds a favor" */
  betterWhen: "higher" | "lower" | null;
  format: (value: number) => string;
  zeroLine?: boolean;
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
    band: "satisfaction",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "attendance",
    title: "Aproveitamento (θ)",
    short: "Aproveitamento (θ)",
    band: "attendance",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "progress",
    title: "Progresso",
    short: "Progresso",
    band: "progress",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "fairness",
    title: "Equidade (índice de Jain, φ)",
    short: "Equidade (φ)",
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
    band: "mean_round",
    bounds: undefined,
    betterWhen: "lower",
    format: formatRatio,
  },
];

export function Comparison({
  run,
  progress,
  onReuseConfig,
}: {
  run: ComparisonRun;
   /** Preenchido só enquanto esta comparação roda: é o card de andamento */
  progress: RunProgress | null;
  onReuseConfig: () => void;
}) {
  const dark = usePrefersDark();
   /** As duas escolhas que governam todos os gráficos: a **régua** do eixo X (período, idade ou coorte) e o **recorte** das linhas (a universidade inteira ou um dos quatro eixos de perfil) */
  const [axisChoice, setAxis] = useState<AxisChoice>("period");
  const [cutChoice, setCut] = useState<CutChoice>("overall");
   /** As cores escolhidas para as faixas, por eixo */
  const [bandColors, setBandColors] = useState(readBandColors);
   /** Quantos pontos a curva por aluno tem: cada um é uma faixa de quantil da coorte */
  const [curvePoints, setCurvePoints] = useState(DEFAULT_CURVE_POINTS);
   /** As duas visualizações, cada uma como a API as devolveu */
  const [series, setSeries] = useState<SeriesPayload | null>(null);
  const [curve, setCurve] = useState<CurvePayload | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

   /** O que o eixo X está mostrando */
  const view: AxisChoice = axisChoice;
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


  const arms: SeriesArmStyle[] = useMemo(
    () =>
      COMPARISON_ARMS.filter((arm) => run.arms.includes(arm.key)).map((arm) => ({
        key: arm.key,
        label: arm.label,
        dash: arm.dash,
      })),
    [run.arms]
  );

  const scattered = view === "grade_average" || view === "reserve";
  const scatterAxis = SCATTER_AXES.find((option) => option.key === view);
  const cuts = CUTS;
  const cut: CutChoice = cuts.some((c) => c.axis === cutChoice)
    ? cutChoice
    : "overall";
  const editableCuts = true;

  // Cada visualização é uma requisição: o SQL já devolve o que vai ser desenhado,
  // e a tela não transforma dado nenhum.
  useEffect(() => {
    let alive = true;
    setSeries(null);
    comparisonSeries(run.id, cut, cutState.applied[cut] ?? [])
      .then((payload) => alive && setSeries(payload))
      .catch((erro) => alive && setFailure((erro as Error).message));
    return () => {
      alive = false;
    };
  }, [run.id, cut, cutState.applied]);

  useEffect(() => {
    if (!scattered) return;
    let alive = true;
    setCurve(null);
    comparisonCurve(run.id, view, curvePoints)
      .then((payload) => alive && setCurve(payload))
      .catch((erro) => alive && setFailure((erro as Error).message));
    return () => {
      alive = false;
    };
  }, [run.id, view, scattered, curvePoints]);

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

   /** Uma linha de edição por corte, da mais alta para a mais baixa, já com a
    * faixa que cada corte abre. A faixa é contada de baixo, como a API as
    * lista, que é o índice em que a cor escolhida fica guardada. */
  const cutRows = cutValues
    .map((value, index) => ({ value, index }))
    .sort((a, b) => b.value - a.value)
    .map((row, position) => ({ ...row, band: cutValues.length - position }));

   /** Onde a faixa de baixo termina: o menor corte, ou o teto do domínio quando não há corte nenhum e a faixa é a população inteira */
  const cutFloor = cutRows.length
    ? cutRows[cutRows.length - 1].value
    : cutHigh;

  const bandColorOf = (band: number) =>
    bandColors[cut]?.[band] ?? bandColor(band, cutValues.length + 1);

  const groupsOf = (armKey: string) => series?.arms[armKey] ?? [];

  const groups = useMemo(
    () =>
      cutGroups(cut, series?.groups ?? [], {
        solo: soloColor(dark),
        bands: bandColors[cut],
      }),
    [series, cut, dark, bandColors]
  );

   /** O recorte "Geral" — o que as métricas que não se partem em faixas usam */
  const soloGroups = useMemo(
    () => cutGroups("overall", [], { solo: soloColor(dark) }),
    [dark]
  );

  const linesOf = (key: string): SeriesLine[] =>
    arms.flatMap((arm) =>
          groupsOf(arm.key).map((group) => ({
            arm: arm.key,
            group: group.group,
            points: (group.x ?? []).flatMap((x, i) => {
              const band = group.values[key]?.[i];
              return band
                ? [{ x, q1: band[0], median: band[1], q3: band[2], n: group.n[i] }]
                : [];
            }),
          }))
        );

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
    return (
      <SeriesChart
        key={id}
        title={title}
        lines={linesOf(key)}
        groups={solo && cut === "overall" ? soloGroups : groups}
        arms={arms}
        runs={run.config.runs}
        xLabel={PERIOD_POINT}
        {...rest}
      />
    );
  };

   /** A métrica sobre a grandeza de vida inteira escolhida: um ponto por faixa de quantil da coorte */
  const metricCurve = (metric: Metric) => {
    if (!scatterAxis || !curve) return null;
    const lines: SeriesLine[] = arms.flatMap((arm) => {
      const points = curve.arms[arm.key]?.[metric.id] ?? [];
      return points.length
        ? [{ group: "overall", arm: arm.key, points }]
        : [];
    });
    if (!lines.length) return null;
    return (
      <SeriesChart
        key={metric.id}
        title={metric.title}
        lines={lines}
        groups={soloGroups}
        arms={arms}
        runs={run.config.runs}
        bounds={metric.bounds}
        format={metric.format}
        xLabel={(x) => `${scatterAxis.label} ${scatterAxis.format(x)}`}
        xBounds={scatterAxis.bounds}
        xFormat={scatterAxis.format}
        axisLabel={scatterAxis.label}
        showCount
        foot="mediana · intervalo interquartil entre os alunos da faixa"
      />
    );
  };

  const metricChart = (metric: Metric) => {
    if (scattered) return metricCurve(metric);
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
      {failure && (
        <div className="error-banner" role="alert">
          {failure}
          <button type="button" className="ghost" onClick={() => setFailure(null)}>
            Fechar
          </button>
        </div>
      )}
      <div className="page-head">
        <div>
          <h1>Comparação de {formatRunDate(run.at)}</h1>
          <p className="note">
            {describeComparison(run)} · {run.seeds * run.arms.length}{" "}
            simulações
            {run.timedOut > 0 &&
              ` · ${run.timedOut} descartadas por tempo, e com elas a seed nos dois braços`}
          </p>
        </div>
        <button className="secondary" onClick={onReuseConfig}>
          Reabrir esta configuração
        </button>
      </div>

      {progress && <RunProgressCard progress={progress} />}

      <div className="rail-layout">
        <div className="rail-layout-main">
        {/* A única seção de gráfico, e por isso sem cabeçalho: não há outra de
            que se distinguir. */}
        <section className="chart-section">
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
            {view === "period" &&
              chart("students", "Alunos medidos", "students", {
                bounds: [0, Infinity],
                format: formatCount,
                solo: true,
              })}
          </div>
        </section>

        {/* Por último, o caso individual. Tudo acima é agregado — a distribuição
            entre as simulações e o perfil dentro delas —, e esta seção é a porta
            de saída para o outro extremo: um aluno, uma disciplina, uma rodada.
            Fica no fim porque custa uma simulação a mais, e porque a pergunta
            que ela responde ("por que este número saiu assim?") só aparece
            depois de ver o número. */}
        <Trace run={run} />

        </div>

        <aside className="rail" aria-label="Visualização">
          <div className="rail-head">
            <h2>Visualização</h2>
          </div>
          <div className="rail-body">
            <div className="rail-field" role="group" aria-label="Eixo">
              <span className="rail-label">Eixo</span>
              <div className="radio-set">
                {[
                  { key: "period" as AxisChoice, label: "Período" },
                  ...SCATTER_AXES.map((option) => ({
                    key: option.key as AxisChoice,
                    label: option.label,
                  })),
                ].map((option) => (
                  <label className="radio" key={option.key}>
                    <input
                      type="radio"
                      name="eixo"
                      checked={view === option.key}
                      onChange={() => setAxis(option.key)}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {scattered && (
              <div className="rail-field">
                <span className="rail-label">Pontos</span>
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
              <div className="rail-field" role="group" aria-label="Linhas">
                <span className="rail-label">Linhas</span>
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
                {/* Uma linha por faixa, da mais alta para a mais baixa: a cor
                    dela, o sinal e o corte que a abre. A última faixa não tem
                    corte próprio — começa em zero e termina onde a de cima
                    abre —, e por isso o campo dela é só leitura. */}
                {cutOption?.field && editableCuts && (
                  <div className="cut-rows">
                    {cutRows.map((row) => (
                      <div className="cut-row" key={row.index}>
                        <input
                          type="color"
                          value={bandColorOf(row.band)}
                          onChange={(e) =>
                            setBandColors(
                              writeBandColor(cut, row.band, e.target.value)
                            )
                          }
                        />
                        <span className="cut-sign">≥</span>
                        <input
                          type="number"
                          min={cutLow}
                          max={Number.isFinite(cutHigh) ? cutHigh : undefined}
                          step={cutOption.step ?? 1}
                          value={row.value.toFixed(cutOption.decimals ?? 0)}
                          onChange={(e) => {
                            const next = [...cutValues];
                            next[row.index] = Number(e.target.value);
                            changeCuts(cut, next);
                          }}
                        />
                        {/* Fecha **esta** faixa contra a de baixo. A última
                            não se apaga: sem corte nenhum não há recorte. */}
                        <button
                          type="button"
                          className="ghost"
                          aria-label="Remover faixa"
                          disabled={cutValues.length <= 1}
                          onClick={() =>
                            changeCuts(
                              cut,
                              cutValues.filter((_, i) => i !== row.index)
                            )
                          }
                        >
                          −
                        </button>
                      </div>
                    ))}
                    <div className="cut-row">
                      <input
                        type="color"
                        value={bandColorOf(0)}
                        onChange={(e) =>
                          setBandColors(writeBandColor(cut, 0, e.target.value))
                        }
                      />
                      <span className="cut-sign">&lt;</span>
                      <input
                        type="number"
                        disabled
                        value={
                          Number.isFinite(cutFloor)
                            ? cutFloor.toFixed(cutOption.decimals ?? 0)
                            : ""
                        }
                      />
                    </div>
                    <div className="cut-actions">
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
                        onClick={() => {
                          let next = bandColors;
                          for (
                            let band = 0;
                            band < cutValues.length + 1;
                            band++
                          ) {
                            next = writeBandColor(cut, band, null);
                          }
                          setBandColors(next);
                        }}
                      >
                        Padrão
                      </button>
                    </div>
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
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
