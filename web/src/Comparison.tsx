import { useMemo, useState } from "react";
import {
  BoxPlot,
  Histogram,
  REQUEST_STATES,
  SeriesChart,
  categoricalColors,
  formatCount,
  formatRatio,
  requestStateColors,
  usePrefersDark,
} from "./charts";
import type { SeriesPoint } from "./charts";
import { boxStats } from "./equations";
import { describeComparison, formatRunDate, ComparisonRun } from "./history";
import { Trace } from "./Trace";
import { COMPARISON_ARMS } from "./types";
import type { CohortSeries, PeriodSeries, RunSummary } from "./types";

/** Períodos com uma casa: o tempo de formatura anda em frações de período, e
 * duas casas sugeririam uma precisão que a amostra não tem. */
const formatPeriods = (value: number) =>
  value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Uma grandeza comparada entre os modelos. É um **acessor**, não uma chave,
 * porque as de saturação não existem como campo: saem de uma posição da lista
 * `allocations_per_round`, e quantas são depende do cenário. */
interface Metric {
  id: string;
  title: string;
  /** Rótulo curto, para a coluna "Métrica" das tabelas. */
  short: string;
  of: (run: RunSummary) => number | null;
  /** Os pontos da grandeza numa simulação, **um acessor por eixo** — o material
   * de que `of` é a média ponderada.
   *
   * O eixo que falta aqui é o eixo em que a grandeza não existe, e é assim que
   * a exclusão fica estrutural em vez de virar um filtro à parte: o tempo de
   * formatura não tem `period` porque é da simulação inteira, e tem `cohort`
   * porque cada aluno pertence a uma coorte só. */
  series?: Partial<Record<SeriesMode, (run: RunSummary) => SeriesPoint[]>>;
  /** Limites naturais da grandeza; o domínio é folgado em torno dos dados mas
   * nunca passa daqui. Ausente quando a grandeza não tem teto. */
  bounds?: [number, number];
  /** De que lado está o melhor resultado — é o que decide o sinal de "seeds a
   * favor". `null` quando a métrica **descreve** em vez de pontuar: λ e a
   * saturação são o caso. Chamar um lado de melhor em λ seria escolher entre
   * alocar por mérito passado e alocar por necessidade; e numa rodada isolada
   * da saturação, "mais alto" tanto pode ser atender mais quanto ter deixado
   * mais para trás — o que se lê ali é o *decaimento* entre as rodadas. */
  betterWhen: "higher" | "lower" | null;
  format: (value: number) => string;
  zeroLine?: boolean;
}

/** Os eixos ordenados sobre os quais uma métrica vira linha — os dois modos
 * de leitura que não são o agregado.
 *
 * O **período** é o tempo: entre o 5 e o 6 há caminho, e o que se lê é a
 * trajetória que a redução resume. A **coorte** é o período de ingresso: o
 * aluno fica na dela do ingresso ao diploma, e o eixo também é ordenado — quem
 * entrou depois encontrou uma universidade mais cheia. É por isso que uma
 * inclinação ali não se lê como efeito do mecanismo, e a comparação que vale é
 * a vertical, entre braços no mesmo ponto. */
type SeriesMode = "period" | "cohort";
type ViewMode = "aggregate" | SeriesMode;

/** Como cada eixo se chama na tela e num ponto dele. */
const AXIS: Record<SeriesMode, { label: string; point: (x: number) => string }> = {
  period: { label: "Por período", point: (x) => `Período ${x}` },
  cohort: { label: "Por coorte", point: (x) => `Coorte ${x}` },
};

/** As listas de um recorte que se desenham como série simples: um número por
 * ponto do eixo. Ficam de fora o próprio eixo — que é `period` ou `cohort` —,
 * excluído na hora do uso, e a saturação, que tem uma dimensão a mais. */
type FlatKeys<T> = {
  [K in keyof T]: T[K] extends (number | null)[] ? K : never;
}[keyof T];

type PeriodValues = Exclude<FlatKeys<PeriodSeries>, "period">;
type CohortValues = Exclude<FlatKeys<CohortSeries>, "cohort">;

/** Os pontos (eixo, valor) de uma lista.
 *
 * Posição nula fica **de fora** em vez de virar zero: ninguém concluiu numa
 * coorte é coisa diferente de ter concluído na hora. Recorte ausente —
 * execução gravada antes dele existir — devolve amostra vazia, e o modo some
 * em vez de desenhar no vazio. */
const pointsOf = (
  axis: number[] | undefined,
  values: (number | null)[] | undefined
): SeriesPoint[] => {
  if (!axis || !values) return [];
  return axis.flatMap((x, index) => {
    const y = values[index];
    return y === null || y === undefined ? [] : [{ x, y }];
  });
};

/** Os pontos de **uma rodada**: a coluna `index` da matriz de saturação, lida
 * ao longo do eixo — a 1ª rodada de cada período (ou de cada coorte), a 2ª de
 * cada um, e assim por diante. */
const columnOf = (
  axis: number[] | undefined,
  matrix: (number | null)[][] | undefined,
  index: number
): SeriesPoint[] =>
  pointsOf(axis, matrix?.map((row) => row?.[index] ?? null));

const byPeriod = (key: PeriodValues) => (run: RunSummary) =>
  pointsOf(run.by_period?.period, run.by_period?.[key]);

const byCohort = (key: CohortValues) => (run: RunSummary) =>
  pointsOf(run.by_cohort?.cohort, run.by_cohort?.[key]);

/** Os pontos de um dos seis estados, em média por aluno.
 *
 * Uma série por estado, **não empilhada**: empilhar torna a espessura de uma
 * faixa legível mas a posição dela dependente de tudo o que está embaixo, e
 * comparar a linha de exclusão entre dois braços com a base balançando é das
 * leituras mais difíceis que existem. Cada estado também ganha escala própria,
 * porque "não elegível" gira numa ordem de grandeza e "excluída" em outra. */
const stateBy =
  (axis: "period" | "cohort", key: (typeof REQUEST_STATES)[number]["key"]) =>
  (run: RunSummary) => {
    const series: PeriodSeries | CohortSeries | undefined =
      axis === "period" ? run.by_period : run.by_cohort;
    const steps =
      axis === "period"
        ? (series as PeriodSeries | undefined)?.period
        : (series as CohortSeries | undefined)?.cohort;
    return pointsOf(
      steps,
      series?.request_states?.map((states) => states?.[key] ?? null)
    );
  };

const roundByPeriod = (index: number) => (run: RunSummary) =>
  columnOf(run.by_period?.period, run.by_period?.allocations_per_round, index);

const roundByCohort = (index: number) => (run: RunSummary) =>
  columnOf(run.by_cohort?.cohort, run.by_cohort?.allocations_per_round, index);

/** As métricas de alocação — as que avaliam a qualidade do que foi alocado.
 *
 * Nada de crédito: orçamento, preço e retorno não existem do lado da linha de
 * base, e comparar um mecanismo com o vazio não compara nada. E nenhum recorte
 * por coorte: aqui a pergunta é sobre o modelo, não sobre o que acontece
 * dentro de cada um.
 *
 * Duas saíram em 08/10. A **ocupação** (θ), porque com o calouro fora do
 * recorte ela deixou de se ler como "o quanto a universidade encheu" — as vagas
 * garantidas continuam ocupadas e não entram mais no numerador; quem quer essa
 * leitura a tem nos gráficos por disciplina de uma simulação. E a
 * **semestralização**, que deu lugar ao tempo de formatura: mede a mesma coisa
 * — progressão na grade — num número que se lê direto. */
const METRICS: Metric[] = [
  {
    id: "efficiency",
    title: "Eficiência de alocação (ψ̄)",
    short: "Eficiência (ψ̄)",
    of: (run) => run.efficiency,
    series: { period: byPeriod("efficiency"), cohort: byCohort("efficiency") },
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "utilization",
    title: "Aproveitamento da carga",
    short: "Aproveitamento",
    of: (run) => run.utilization,
    series: { period: byPeriod("utilization"), cohort: byCohort("utilization") },
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "fidelity",
    title: "Fidelidade da mensagem",
    short: "Fidelidade",
    of: (run) => run.fidelity,
    series: { period: byPeriod("fidelity"), cohort: byCohort("fidelity") },
    bounds: [0, 1],
    // Descreve, não pontua: dizer qual lado é melhor exigiria escolher entre
    // expressar intensidade e ser simples de usar, e isso é juízo de quem lê.
    betterWhen: null,
    format: formatRatio,
  },
  {
    id: "fairness",
    title: "Equidade (índice de Jain, φ)",
    short: "Equidade (φ)",
    of: (run) => run.fairness,
    series: { period: byPeriod("fairness"), cohort: byCohort("fairness") },
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "exclusion_rate",
    title: "Desperdício de vaga",
    short: "Desperdício",
    of: (run) => run.exclusion_rate,
    series: {
      period: byPeriod("exclusion_rate"),
      cohort: byCohort("exclusion_rate"),
    },
    bounds: [0, 1],
    // A vaga que ninguém cursou é perda pura: saiu da oferta e não virou aula.
    betterWhen: "lower",
    format: formatRatio,
  },
  {
    id: "correlation",
    title: "Correlação CR × satisfação (λ)",
    short: "Correlação (λ)",
    of: (run) => run.correlation,
    series: { period: byPeriod("correlation"), cohort: byCohort("correlation") },
    bounds: [-1, 1],
    betterWhen: null,
    format: formatRatio,
    zeroLine: true,
  },
  {
    id: "graduation_rate",
    title: "Fração de concluintes",
    short: "Concluintes",
    of: (run) => (run.population ? run.graduates / run.population : null),
    // Fração, e não contagem: o absoluto depende do tamanho do ingresso, e os
    // braços só são comparáveis na mesma escala.
    //
    // **Não há gráfico de jubilados ao lado.** Como o horizonte é derivado do
    // ciclo de vida, ao fim dele todo mundo saiu por uma das duas portas, e a
    // fração de jubilados é exatamente `1 − esta`. Seria a mesma curva
    // espelhada, ocupando espaço e convidando a ler duas vezes o mesmo fato.
    series: { cohort: byCohort("graduation_rate") },
    betterWhen: "higher",
    bounds: [0, 1],
    format: formatRatio,
  },
  {
    id: "time_to_graduate",
    title: "Tempo de formatura (períodos)",
    short: "Tempo (períodos)",
    of: (run) => run.time_to_graduate,
    // Sem `period`: o tempo é da simulação inteira, e a versão por período
    // ("quanto levou quem concluiu em t") seria outra grandeza, com viés de
    // sobrevivência. Por coorte ele existe — cada aluno pertence a uma só.
    series: { cohort: byCohort("time_to_graduate") },
    betterWhen: "lower",
    format: formatPeriods,
  },
];


/** O que cada modo mostra, em uma linha. Fica junto das métricas e não dentro
 * do JSX porque é texto de leitura, não marcação: é onde a ressalva de cada
 * eixo está escrita. */
const NOTES: Record<ViewMode, { metrics: string; saturation: string }> = {
  aggregate: {
    metrics:
      "Cada caixa é a distribuição da métrica sobre as simulações do modelo; o que se compara é a sobreposição delas, não a distância entre as medianas.",
    saturation:
      "Um gráfico por rodada, e o que se lê entre eles é o decaimento: quem atende mais demanda cedo começa alto e cai rápido.",
  },
  period: {
    metrics:
      "A mediana entre as simulações em cada período, com o intervalo interquartil em faixa. O tempo de formatura não entra: é da simulação inteira, não do período.",
    saturation:
      "A mesma rodada ao longo do horizonte — a 1ª rodada de cada período, a 2ª de cada período —, para o decaimento se ler junto com o momento em que acontece.",
  },
  cohort: {
    metrics:
      "A mediana entre as simulações em cada coorte: quem entrou no período 1, no 2, e assim por diante. As coortes não são intercambiáveis — a primeira encontra a universidade quase vazia e a última a encontra cheia —, então a inclinação ao longo do eixo mistura mecanismo e mercado. O que se lê aqui é a comparação entre os braços num mesmo ponto.",
    saturation:
      "A mesma rodada em cada coorte — a 1ª rodada de cada uma, a 2ª de cada uma.",
  },
};

const ORDINALS = ["1ª", "2ª", "3ª", "4ª", "5ª", "6ª", "7ª", "8ª", "9ª", "10ª"];

/** Uma métrica por rodada do cenário: as vagas obtidas por aluno naquela
 * rodada. Quantas são depende do |R| da simulação, então elas são construídas a
 * partir do resultado, e não de uma lista fixa. */
const roundMetrics = (rounds: number): Metric[] =>
  Array.from({ length: rounds }, (_, index) => {
    const ordinal = ORDINALS[index] ?? `${index + 1}ª`;
    return {
      id: `round-${index}`,
      title: `Alocações por aluno (${ordinal} rodada)`,
      short: `Alocações (${ordinal} rodada)`,
      of: (run) => run.allocations_per_round?.[index] ?? null,
      series: { period: roundByPeriod(index), cohort: roundByCohort(index) },
      bounds: [0, Infinity],
      betterWhen: null,
      format: formatCount,
    };
  });

/** Os dois braços do leilão que isolam o retorno: eles diferem em **uma**
 * coisa só — `credits_ilp` é o leilão com PLI e sem retorno, `credits_return`
 * é o mesmo com a política proporcional. Comparar qualquer outro par mediria
 * o retorno somado a outra diferença. */
const WITH_RETURN = "credits_return";
const WITHOUT_RETURN = "credits_ilp";

/** A linha de base, contra a qual as diferenças da tabela de resumo são
 * medidas: a matrícula por CR com varredura, que é o mecanismo real das
 * universidades brasileiras. */
const BASELINE = "ranking_greedy";

/** Sinal explícito: numa coluna de diferenças, "+0,04" e "−0,04" se distinguem
 * de relance e "0,04" não. */
/** Os rótulos dos braços, na ordem do caminho. Derivado de uma constante do
 * módulo, então não precisa ser recalculado a cada render. */
const ARM_LABELS = COMPARISON_ARMS.map((arm) => arm.label);

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
  const colors = useMemo(() => categoricalColors(ARM_LABELS, dark), [dark]);
  const stateColors = useMemo(() => requestStateColors(dark), [dark]);
  /** Os dois modos de ler as métricas de alocação. O agregado é o padrão: é
   * nele que a pergunta "qual modelo?" se responde, e o por período é a
   * pergunta seguinte — *onde* no horizonte mora o vão. */
  const [view, setView] = useState<ViewMode>("aggregate");

  /** A escada de ablação só roda quando pedida (`ARMS + ABLATION_ARMS` no
   * motor). Sem os dois braços do leilão não há o que isolar, e a tabela do
   * retorno sairia inteira em traços. */
  const hasAblation = [WITH_RETURN, WITHOUT_RETURN].every((key) =>
    result.arms.some((arm) => arm.key === key)
  );

  /** Quais eixos esta comparação traz. As gravadas antes de um recorte existir
   * não o trazem, e aí o botão dele some — como a saturação some quando falta
   * a lista de rodadas. */
  const available = useMemo(
    () => ({
      period: result.arms.some((arm) =>
        arm.runs.some((entry) => entry.by_period?.period.length)
      ),
      cohort: result.arms.some((arm) =>
        arm.runs.some((entry) => entry.by_cohort?.cohort.length)
      ),
    }),
    [result.arms]
  );
  const modes = (Object.keys(AXIS) as SeriesMode[]).filter((axis) => available[axis]);
  const mode: ViewMode = view === "aggregate" || available[view] ? view : "aggregate";

  /** As execuções de um braço, na ordem das seeds. Execuções gravadas antes de
   * um braço existir simplesmente não o trazem, e o braço sai vazio em vez de
   * derrubar a tela. */
  const runsOf = (key: string): RunSummary[] =>
    result.arms.find((arm) => arm.key === key)?.runs ?? [];

  /** As duas distribuições de entrada do cenário. Não variam entre braços nem
   * entre seeds: são do cenário, não da simulação. */
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

  /** Quantas rodadas o cenário teve, lido do próprio resultado. Comparações
   * gravadas antes da saturação existir não trazem a lista, e aí a seção some
   * em vez de aparecer vazia. */
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

  /** Os valores de uma métrica numa amostra. Posições nulas (ninguém concluiu,
   * rodada sem o que medir) ficam de fora — zero ali seria um valor medido. */
  const valuesOf = (key: string, metric: Metric): number[] =>
    runsOf(key)
      .map(metric.of)
      .filter((value): value is number => value !== null && value !== undefined);

  /** Comparação pareada entre dois braços: em quantas das N seeds o primeiro
   * saiu melhor que o segundo. Só faz sentido porque as listas compartilham a
   * seed — é a mesma população dos dois lados, e a comparação par a par não
   * precisa supor nada sobre a forma das distribuições. Pares incompletos não
   * contam nem a favor nem contra. */
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

  /** Quantas seeds o retorno fez *subir* — contagem descritiva, sem juízo de
   * melhor ou pior, porque para λ e para a saturação não há um lado bom. */
  const raisedByReturn = (metric: Metric) => {
    const a = runsOf(WITH_RETURN);
    const b = runsOf(WITHOUT_RETURN);
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

  /** Uma linha por braço na tabela de resumo. */
  const summaryRows = (metric: Metric) =>
    COMPARISON_ARMS.map((arm, index) => {
      const box = boxStats(valuesOf(arm.key, metric));
      const baseline = medianOf(BASELINE, metric);
      const pairing = arm.key === BASELINE ? null : paired(metric, arm.key, BASELINE);
      return (
        <tr key={`${metric.id}-${arm.key}`}>
          {/* O nome da métrica só na primeira das três linhas: repetido ele
              viraria ruído entre números que se comparam. */}
          <td>{index === 0 ? metric.short : ""}</td>
          <td>
            <span className="swatch" style={{ background: colors[arm.label] }} /> {arm.label}
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

  /** Uma linha por métrica na tabela do efeito do retorno. */
  const returnRow = (metric: Metric) => {
    const without = medianOf(WITHOUT_RETURN, metric);
    const withReturn = medianOf(WITH_RETURN, metric);
    const baseline = medianOf(BASELINE, metric);
    const { up, comparable } = raisedByReturn(metric);
    return (
      <tr key={metric.id}>
        <td>{metric.short}</td>
        <td>{without === null ? "—" : metric.format(without)}</td>
        <td>{withReturn === null ? "—" : metric.format(withReturn)}</td>
        <td>
          {without === null || withReturn === null
            ? "—"
            : formatDelta(withReturn - without, metric.format)}
        </td>
        <td>{`${up}/${comparable}`}</td>
        <td className="muted-cell">{baseline === null ? "—" : metric.format(baseline)}</td>
      </tr>
    );
  };

  /** As amostras de uma grandeza por braço, uma lista de pontos por simulação —
   * o que o gráfico de séries resume em mediana e faixa. */
  const samplesOf = (of: (run: RunSummary) => SeriesPoint[]) =>
    COMPARISON_ARMS.map((arm) => ({
      label: arm.label,
      samples: runsOf(arm.key).map(of),
    }));

  /** Um gráfico de séries avulso — o que não é métrica mas se lê no mesmo
   * eixo: o peso de cada ponto, os concluintes de cada coorte. */
  const chartOfSeries = (
    id: string,
    title: string,
    axis: SeriesMode,
    of: (run: RunSummary) => SeriesPoint[],
    extra: { bounds?: [number, number]; format?: (value: number) => string } = {}
  ) => (
    <SeriesChart
      key={id}
      title={title}
      groups={samplesOf(of)}
      colors={colors}
      runs={result.runs}
      xLabel={AXIS[axis].point}
      {...extra}
    />
  );

  const seriesFor = (metric: Metric, axis: SeriesMode) => {
    const of = metric.series?.[axis];
    if (!of) return null;
    return (
      <SeriesChart
        key={metric.id}
        title={metric.title}
        groups={samplesOf(of)}
        colors={colors}
        bounds={metric.bounds}
        format={metric.format}
        zeroLine={metric.zeroLine}
        runs={result.runs}
        xLabel={AXIS[axis].point}
      />
    );
  };

  const chartFor = (metric: Metric) => (
    <BoxPlot
      key={metric.id}
      title={metric.title}
      groups={COMPARISON_ARMS.map((arm) => ({
        label: arm.label,
        short: arm.short,
        values: valuesOf(arm.key, metric),
      }))}
      colors={colors}
      bounds={metric.bounds}
      format={metric.format}
      zeroLine={metric.zeroLine}
    />
  );

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
        {/* Um alternador para a tela inteira, e não um por seção: o que ele
            troca é o eixo horizontal dos gráficos, e lê-los com eixos
            diferentes lado a lado é o que não se quer. */}
        {modes.length > 0 && (
          <div className="view-switch">
            <button
              type="button"
              className={mode === "aggregate" ? "on" : ""}
              onClick={() => setView("aggregate")}
            >
              Agregado
            </button>
            {modes.map((axis) => (
              <button
                key={axis}
                type="button"
                className={mode === axis ? "on" : ""}
                onClick={() => setView(axis)}
              >
                {AXIS[axis].label}
              </button>
            ))}
          </div>
        )}
      </div>

      <section className="chart-section">
        <header className="chart-section-head">
          <h2>Métricas de alocação</h2>
          <p>{NOTES[mode].metrics}</p>
        </header>
        <div className="chart-grid">
          {mode === "aggregate"
            ? METRICS.map(chartFor)
            : [
                ...METRICS.map((metric) => seriesFor(metric, mode)),
                // O contexto do eixo, no fim da grade: o peso de cada ponto.
                // Ele mostra as três fases do horizonte — a universidade
                // enchendo, o estado estacionário e a drenagem —, e sem ele a
                // queda das curvas no fim se leria como mudança de mecanismo.
                //
                // Só no período. Na coorte o contexto é o concluinte, e ele
                // **já está na grade como métrica** (`graduation_rate`):
                // repeti-lo aqui desenhava a mesma curva duas vezes.
                mode === "period"
                  ? chartOfSeries("students", "Alunos ativos", mode, byPeriod("students"), {
                      bounds: [0, Infinity],
                      format: formatCount,
                    })
                  : null,
              ]}
        </div>
      </section>

      {rounds > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>Saturação da demanda</h2>
            <p>{NOTES[mode].saturation}</p>
          </header>
          <div className="chart-grid">
            {mode === "aggregate"
              ? saturation.map(chartFor)
              : saturation.map((metric) => seriesFor(metric, mode))}
          </div>
        </section>
      )}

      {mode !== "aggregate" && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>Solicitações de disciplinas</h2>
            <p>
              Em que estado terminou cada disciplina que ainda falta ao aluno, em
              média por aluno. Os seis particionam o que falta — o catálogo menos
              o que ele já aprovou —, então somá-los dá o tamanho desse
              denominador. Uma escala por estado: lê-se a diferença entre os
              modelos <em>dentro</em> de cada painel, nunca a altura entre eles.
            </p>
          </header>
          <div className="chart-grid">
            {REQUEST_STATES.map((state) => (
              <SeriesChart
                key={state.key}
                title={state.label}
                accent={stateColors[state.key]}
                groups={samplesOf(stateBy(mode, state.key))}
                colors={colors}
                bounds={[0, Infinity]}
                format={formatCount}
                runs={result.runs}
                xLabel={AXIS[mode].point}
              />
            ))}
          </div>
        </section>
      )}

      {scenarioHistograms.length > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>As distribuições do cenário</h2>
          </header>
          <div className="chart-grid">{scenarioHistograms}</div>
        </section>
      )}

      {hasAblation && (
      <div className="panel">
        <h2>O que o retorno de créditos muda</h2>
        <table>
          <thead>
            <tr>
              <th>Métrica</th>
              <th>Sem retorno</th>
              <th>Com retorno</th>
              <th>Efeito do retorno</th>
              <th>Subiu em</th>
              <th>CR (referência)</th>
            </tr>
          </thead>
          <tbody>{[...METRICS, ...saturation].map(returnRow)}</tbody>
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
              const row = COMPARISON_ARMS.map((arm) => runsOf(arm.key)[i]).filter(Boolean);
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
