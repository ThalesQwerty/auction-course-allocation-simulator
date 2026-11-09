import { useMemo, useState } from "react";
import {
  Histogram,
  LineSample,
  REQUEST_STATES,
  SeriesChart,
  categoricalColors,
  formatCount,
  formatRatio,
  inkFor,
  requestStateColors,
  soloColor,
  usePrefersDark,
} from "./charts";
import type { SeriesArmStyle, SeriesLine } from "./charts";
import { CUTS, cutGroups, seriesOf } from "./bands";
import { boxStats } from "./equations";
import { describeComparison, formatRunDate, ComparisonRun } from "./history";
import { Trace } from "./Trace";
import { COMPARISON_ARMS } from "./types";
import type { CutAxis, RunSummary } from "./types";

/** Períodos com uma casa: o tempo de formatura anda em frações de período, e
 * duas casas sugeririam uma precisão que a amostra não tem. */
const formatPeriods = (value: number) =>
  value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Uma grandeza comparada entre os modelos. `of` é o ponto de uma simulação,
 * que as tabelas usam; `band` é a chave da série por período em
 * `GroupBands.values`, que os gráficos desenham. Sem `band` a métrica fica só
 * nas tabelas — é o caso do tempo de formatura, que é da simulação inteira. */
interface Metric {
  id: string;
  title: string;
  /** Rótulo curto, para a coluna "Métrica" das tabelas. */
  short: string;
  of: (run: RunSummary) => number | null;
  band?: string;
  /** Limites naturais da grandeza; o domínio é folgado em torno dos dados mas
   * nunca passa daqui. Ausente quando a grandeza não tem teto. */
  bounds?: [number, number];
  /** De que lado está o melhor resultado — é o que decide o sinal de "seeds a
   * favor". `null` quando a métrica **descreve** em vez de pontuar: λ e a
   * saturação são o caso. */
  betterWhen: "higher" | "lower" | null;
  format: (value: number) => string;
  zeroLine?: boolean;
}

/** O traçado de cada modelo: contínuo para o leilão, tracejado para o CR. A
 * cor fica livre para o grupo do recorte. */
const ARM_DASH: Record<string, string> = {
  ranking_greedy: "6 4",
  credits_return: "",
};

/** As métricas de alocação — as que avaliam a qualidade do que foi alocado.
 *
 * Nada de crédito: orçamento, preço e retorno não existem do lado da linha de
 * base, e comparar um mecanismo com o vazio não compara nada.
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
    band: "efficiency",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "utilization",
    title: "Aproveitamento da carga",
    short: "Aproveitamento",
    of: (run) => run.utilization,
    band: "utilization",
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
    // A vaga que ninguém cursou é perda pura: saiu da oferta e não virou aula.
    betterWhen: "lower",
    format: formatRatio,
  },
  {
    id: "correlation",
    title: "Correlação CR × satisfação (λ)",
    short: "Correlação (λ)",
    of: (run) => run.correlation,
    band: "correlation",
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
    //
    // Por período ela é **acumulada**: quem concluiu até ali sobre quem já
    // tinha entrado. No último período é o número da tabela.
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
    // Sem série: o tempo é da simulação inteira, e a versão por período
    // ("quanto levou quem concluiu em t") seria outra grandeza, com viés de
    // sobrevivência. Fica nas tabelas.
    betterWhen: "lower",
    format: formatPeriods,
  },
];


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
      band: `round_${index + 1}`,
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
  const stateColors = useMemo(() => requestStateColors(dark), [dark]);
  /** O recorte dos gráficos: a universidade inteira, a coorte ou um dos
   * quatro eixos de perfil. Um para a tela inteira — o que ele troca são as
   * linhas de todos os gráficos, e lê-los com recortes diferentes lado a lado
   * é o que não se quer. */
  const [cutChoice, setCut] = useState<CutAxis>("overall");

  /** A escada de ablação só roda quando pedida (`ARMS + ABLATION_ARMS` no
   * motor). Sem os dois braços do leilão não há o que isolar, e a tabela do
   * retorno sairia inteira em traços. */
  const hasAblation = [WITH_RETURN, WITHOUT_RETURN].every((key) =>
    result.arms.some((arm) => arm.key === key)
  );

  /** Os modelos que rodaram, com o traçado de cada um. */
  const arms: SeriesArmStyle[] = useMemo(
    () =>
      COMPARISON_ARMS.filter((arm) => result.arms.some((a) => a.key === arm.key)).map(
        (arm) => ({ key: arm.key, label: arm.label, dash: ARM_DASH[arm.key] ?? "2 3" })
      ),
    [result.arms]
  );

  /** As séries de cada braço, por recorte. */
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

  /** Os recortes que esta comparação traz. Uma gravada antes dos recortes por
   * perfil só tem o "Geral", e os outros botões somem. */
  const cuts = CUTS.filter((cut) =>
    Object.values(series).some((axes) =>
      axes.some((a) => a.axis === cut.axis && a.groups.length)
    )
  );
  const cut: CutAxis = cuts.some((c) => c.axis === cutChoice)
    ? cutChoice
    : (cuts[0]?.axis ?? "overall");

  /** Os grupos do recorte, com cor e rótulo. */
  const groups = useMemo(() => {
    const present = [
      ...new Set(
        Object.values(series).flatMap(
          (axes) => axes.find((a) => a.axis === cut)?.groups.map((g) => g.group) ?? []
        )
      ),
    ];
    return cutGroups(cut, run.config, present, {
      solo: soloColor(dark),
      categorical: (labels) => categoricalColors(labels, dark),
    });
  }, [series, cut, run.config, dark]);

  /** As linhas de uma grandeza: um grupo do recorte sob um modelo. */
  const linesOf = (key: string): SeriesLine[] =>
    arms.flatMap((arm) =>
      (series[arm.key]?.find((a) => a.axis === cut)?.groups ?? []).map((group) => ({
        arm: arm.key,
        group: group.group,
        points: group.period.flatMap((x, i) => {
          const band = group.values[key]?.[i];
          return band
            ? [{ x, q1: band[0], median: band[1], q3: band[2], n: group.n[i] }]
            : [];
        }),
      }))
    );

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
            <LineSample dash={ARM_DASH[arm.key] ?? "2 3"} color={ink.secondary} />{" "}
            {arm.label}
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

  /** Um gráfico de séries por período, no recorte escolhido. */
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
      arms={arms}
      runs={result.runs}
      xLabel={(x) => `Período ${x}`}
      {...extra}
    />
  );

  const metricChart = (metric: Metric) =>
    metric.band
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
        {cuts.length > 1 && (
          <div className="view-switch">
            {cuts.map((option) => (
              <button
                key={option.axis}
                type="button"
                className={cut === option.axis ? "on" : ""}
                onClick={() => setCut(option.axis)}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <section className="chart-section">
        <header className="chart-section-head">
          <h2>Métricas de alocação</h2>
          <p>
            A mediana entre as simulações em cada período, com o intervalo
            interquartil em faixa. O tempo de formatura não entra: é da
            simulação inteira, não do período.
          </p>
        </header>
        <div className="chart-grid">
          {METRICS.map(metricChart)}
          {/* O peso de cada ponto, no fim da grade. Ele mostra as três fases
              do horizonte — a universidade enchendo, o estado estacionário e
              a drenagem —, e sem ele a queda das curvas no fim se leria como
              mudança de mecanismo. */}
          {chart("students", "Alunos ativos", "students", {
            bounds: [0, Infinity],
            format: formatCount,
          })}
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
          {REQUEST_STATES.map((state) =>
            chart(state.key, state.label, state.key, {
              accent: stateColors[state.key],
              bounds: [0, Infinity],
              format: formatCount,
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
