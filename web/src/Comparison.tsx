import { useMemo } from "react";
import {
  BoxPlot,
  Histogram,
  MetricChart,
  boxStats,
  categoricalColors,
  formatCount,
  formatRatio,
  usePrefersDark,
} from "./charts";
import type { SeriesPoint } from "./charts";
import { describeComparison, formatRunDate, ComparisonRun } from "./history";
import { COMPARISON_ARMS } from "./types";
import type { ArmResult, RunSummary, Sweep } from "./types";

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
  hint: string;
  of: (run: RunSummary) => number | null;
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

/** As métricas de alocação — as que avaliam a qualidade do que foi alocado.
 *
 * Nada de crédito: orçamento, preço e retorno não existem do lado da linha de
 * base, e comparar um mecanismo com o vazio não compara nada. E nenhum recorte
 * por geração: aqui a pergunta é sobre o modelo, não sobre o que acontece
 * dentro de cada um.
 *
 * Duas saíram em 08/10. A **ocupação** (θ), porque com o calouro fora do
 * recorte ela deixou de se ler como "o quanto a universidade encheu" — as vagas
 * garantidas continuam ocupadas e não entram mais no numerador; quem quer essa
 * leitura a tem nos gráficos por disciplina de uma execução. E a
 * **semestralização**, que deu lugar ao tempo de formatura: mede a mesma coisa
 * — progressão na grade — num número que se lê direto. */
const METRICS: Metric[] = [
  {
    id: "efficiency",
    title: "Eficiência de alocação (ψ̄)",
    short: "Eficiência (ψ̄)",
    hint: "Satisfação média dos alunos que disputaram — eq. (53). A utilidade é zero fora do conjunto elegível, então ψ é a fração do que o aluno podia cursar e conseguiu",
    of: (run) => run.efficiency,
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "fairness",
    title: "Equidade (índice de Jain, φ)",
    short: "Equidade (φ)",
    hint: "1 = todos igualmente satisfeitos — eq. (55)",
    of: (run) => run.fairness,
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "correlation",
    title: "Correlação CR × satisfação (λ)",
    short: "Correlação (λ)",
    hint: "Positivo = quem tem CR maior se sai melhor — eq. (57). É aqui que se lê o mérito: a linha de base o impõe por construção (o CR é o critério), o leilão sem retorno o ignora, e o leilão com retorno está em algum ponto entre os dois. Descreve, não pontua — qual lado é melhor depende de alocar por mérito passado ou por necessidade, e isso o gráfico não decide",
    of: (run) => run.correlation,
    bounds: [-1, 1],
    betterWhen: null,
    format: formatRatio,
    zeroLine: true,
  },
  {
    id: "time_to_graduate",
    title: "Tempo de formatura (períodos)",
    short: "Tempo (períodos)",
    hint: "Períodos do ingresso ao diploma, na média dos concluintes — menor é melhor. Tem viés de seleção: só existe sobre quem concluiu, então um modelo que forma menos gente pode exibir um tempo menor só porque sobraram os rápidos. Não se lê sem a coluna de formados da tabela abaixo",
    of: (run) => run.time_to_graduate,
    betterWhen: "lower",
    format: formatPeriods,
  },
];

/** Formandos entra **só na varredura**, e não no boxplot. O motivo é o achado
 * que a varredura revelou: ψ̄ sobe monotonicamente conforme a preferência
 * concentra e chega perto de 1 na ponta, onde ninguém se forma — o aluno quer
 * uma disciplina só, consegue, e a satisfação dele é plena. ψ̄ é satisfação
 * *relativa ao que o aluno queria*, então ela é cega para essa patologia, e a
 * contagem de formandos é a única métrica que a pega. Lado a lado no mesmo eixo
 * x, as duas contam a troca que o mecanismo faz. */
const GRADUATES: Metric = {
  id: "graduates",
  title: "Formandos",
  short: "Formandos",
  hint: "Quantos concluíram o curso no horizonte. Sem ele, ψ̄ sozinha diria que concentrar a preferência é sempre melhor — e no extremo ela chega perto de 1 justamente onde ninguém se forma",
  of: (run) => run.graduates,
  bounds: [0, Infinity],
  betterWhen: "higher",
  format: formatCount,
};

const ORDINALS = ["1ª", "2ª", "3ª", "4ª", "5ª", "6ª", "7ª", "8ª", "9ª", "10ª"];

/** Uma métrica por rodada do cenário: as vagas obtidas por aluno naquela
 * rodada. Quantas são depende do |R| da execução, então elas são construídas a
 * partir do resultado, e não de uma lista fixa. */
const roundMetrics = (rounds: number): Metric[] =>
  Array.from({ length: rounds }, (_, index) => {
    const ordinal = ORDINALS[index] ?? `${index + 1}ª`;
    return {
      id: `round-${index}`,
      title: `Alocações por aluno (${ordinal} rodada)`,
      short: `Alocações (${ordinal} rodada)`,
      hint:
        index === 0
          ? "Vagas conquistadas por aluno na primeira rodada. É o que o mecanismo consegue atender de saída, com a oferta ainda intocada — e quanto mais alto, mais da demanda do período já saiu daqui"
          : `Vagas conquistadas por aluno na ${ordinal} rodada, e só nela — não é acumulado. Quanto mais baixo em relação à primeira, mais a demanda já tinha sido atendida antes de chegar aqui`,
      of: (run) => run.allocations_per_round?.[index] ?? null,
      bounds: [0, Infinity],
      betterWhen: null,
      format: formatCount,
    };
  });

/** Os dois braços do leilão, na ordem em que a diferença entre eles se lê: o
 * retorno é o que muda de um para o outro. */
const WITH_RETURN = "credits_return";
const WITHOUT_RETURN = "credits";
/** A linha de base, contra a qual as diferenças da tabela principal são
 * medidas. */
const BASELINE = "ranking";

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

  const labels = COMPARISON_ARMS.map((arm) => arm.label);
  const colors = useMemo(() => categoricalColors(labels, dark), [dark, labels.join()]);

  /** As execuções de um braço, na ordem das seeds. Execuções gravadas antes de
   * um braço existir simplesmente não o trazem, e o braço sai vazio em vez de
   * derrubar a tela. */
  const runsOf = (key: string): RunSummary[] =>
    result.arms.find((arm) => arm.key === key)?.runs ?? [];

  /** As duas distribuições de entrada do cenário. A de utilidades só entra
   * aqui quando **não** há varredura — com varredura ela tem seção própria, uma
   * por sigma. A de notas entra sempre, porque não depende de sigma: varrida,
   * ela sairia idêntica em todos os pontos. */
  const scenarioHistograms = [
    result.grade_distribution?.length ? (
      <Histogram
        key="notas"
        title="Notas de primeira tentativa"
        hint="a normal do cenário, truncada em [0, 10]"
        fractions={result.grade_distribution}
        domain={[0, 10]}
      />
    ) : null,
    !result.sweep && result.utility_distribution?.length ? (
      <Histogram
        key="utilidades"
        title="Utilidades"
        hint="como a preferência de um aluno se reparte entre as disciplinas"
        fractions={result.utility_distribution}
      />
    ) : null,
  ].filter(Boolean);

  /** A varredura, quando a execução a pediu. Comparações gravadas antes dela
   * existir simplesmente não a trazem, e a seção some em vez de aparecer
   * vazia. */
  const sweep: Sweep | null = result.sweep ?? null;

  /** Um ponto por sigma, com uma coluna por braço — o formato que o
   * `MetricChart` consome. O valor de cada braço é a **mediana** das execuções
   * daquele ponto: com poucas execuções por ponto a média seria arrastada por
   * uma só, e o que interessa aqui é a tendência. */
  const sweepSeries = (metric: Metric): SeriesPoint[] =>
    (sweep?.points ?? []).map((point) => {
      const row: SeriesPoint = { x: point.sigma };
      for (const arm of COMPARISON_ARMS) {
        const found: ArmResult | undefined = point.arms.find((a) => a.key === arm.key);
        const values = (found?.runs ?? [])
          .map(metric.of)
          .filter((value): value is number => value !== null && Number.isFinite(value))
          .sort((a, b) => a - b);
        if (values.length) {
          const middle = Math.floor(values.length / 2);
          row[arm.label] =
            values.length % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2;
        }
      }
      return row;
    });

  /** Marcas do eixo: uma por ponto. Com mais de 8 pontos elas colidem, e aí
   * ficam uma sim uma não — o eixo é contínuo, então pular marca não esconde
   * dado. */
  const sweepTicks = (sweep?.points ?? [])
    .map((point) => point.sigma)
    .filter((_, index, all) => all.length <= 8 || index % 2 === 0);
  const formatSigma = (value: number) =>
    value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });

  const sweepChartFor = (metric: Metric) => (
    <MetricChart
      key={`sweep-${metric.id}`}
      title={metric.title}
      hint={metric.hint}
      data={sweepSeries(metric)}
      series={labels}
      colors={colors}
      domain={metric.bounds ? [metric.bounds[0], metric.bounds[1] === Infinity ? "auto" : metric.bounds[1]] : undefined}
      format={metric.format}
      zeroLine={metric.zeroLine}
      numericX
      xTicks={sweepTicks}
      xFormat={formatSigma}
      xReference={sweep?.canonical}
    />
  );

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

  const chartFor = (metric: Metric) => (
    <BoxPlot
      key={metric.id}
      title={metric.title}
      hint={metric.hint}
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

      <div className="panel">
        <h2>
          {result.runs} execuções de cada modelo — {result.runs * result.arms.length}{" "}
          simulações
        </h2>
        <p className="note">
          Três modelos sobre o mesmo cenário. O leilão entra <strong>duas vezes</strong>, com e sem
          retorno de créditos, porque o retorno é o que pode devolver ao mecanismo algum senso
          meritocrático: na política proporcional quem aprova recupera a fatia do preço
          correspondente à nota, então ir bem compra poder de compra no período seguinte. A
          ordenação por CR faz isso por construção — o histórico <em>é</em> o critério —, e o
          leilão sem retorno não faz de jeito nenhum.
        </p>
        <ul className="note">
          {COMPARISON_ARMS.map((arm) => (
            <li key={arm.key}>
              <span className="swatch" style={{ background: colors[arm.label] }} />{" "}
              <strong>{arm.label}</strong> — {arm.hint}
            </li>
          ))}
        </ul>
        <p className="note">
          As seeds vão de <strong>1 a {result.runs}</strong> e são <strong>pareadas</strong>: a
          i-ésima execução de cada modelo parte da mesma população, da mesma matriz de utilidades e
          da mesma matriz de notas. É a condição metodológica da Seção 7.3 — todos recebem a mesma
          inicialização, e por isso a diferença entre eles é atribuível ao <strong>modelo</strong>,
          não ao sorteio nem às particularidades de um cenário.
        </p>
        <p className="note">
          Cada caixa é a distribuição da métrica sobre as {result.runs} execuções daquele modelo: a
          linha grossa é a <strong>mediana</strong>, a caixa é a metade central da amostra (1º ao 3º
          quartil), os bigodes vão até 1,5 IQR e o que sobra aparece como ponto solto. Uma execução
          vale a média dos períodos <strong>ponderada pelos alunos medidos</strong> — a simulação
          termina numa fase de drenagem, e sem o peso um período final de poucos alunos contaria
          tanto quanto um período cheio. O tempo de formatura é a exceção: não é de período, é da
          execução inteira.
        </p>
        <p className="note">
          <strong>Quem acabou de ingressar não entra em métrica nenhuma.</strong> O calouro
          recebe um pacote fixo — as disciplinas de entrada —, igual para todo mundo e indiferente
          à preferência, e pontua CR = 0 por construção. O ψ dele mede só o quanto o gosto
          sorteado coincidiu com o pacote (vale 1 quando não há optativa no cenário, e cai para a
          faixa de 0,2 quando há). Nos dois casos é a matrícula garantida que estaria sendo
          medida, e não a alocação — igual nos três modelos.
        </p>
      </div>

      <section className="chart-section">
        <header className="chart-section-head">
          <h2>Métricas de alocação</h2>
          <p>
            Caixas que não se tocam separam os modelos; caixas sobrepostas dizem que a diferença
            entre as medianas cabe dentro da variação entre populações
          </p>
        </header>
        <div className="chart-grid">{METRICS.map(chartFor)}</div>
      </section>

      {rounds > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>Saturação da demanda</h2>
            <p>
              Vagas obtidas por aluno em cada rodada, uma caixa por modelo. Cada gráfico conta o
              que foi ganho <strong>naquela</strong> rodada, não o acumulado — somados, os{" "}
              {rounds} dão as vagas por aluno do período
            </p>
          </header>
          <p className="note">
            O que se lê aqui é o <strong>decaimento</strong> entre os gráficos, não o nível de cada
            um. Um mecanismo que atende mais demanda de saída começa alto e cai rápido: sobra pouco
            para as rodadas seguintes porque pouco ficou por alocar. Um que leva a disputa adiante
            distribui as vagas pelas rodadas. Por isso nenhuma rodada isolada tem lado "melhor" —
            na primeira, mais alto é atender mais; nas seguintes, mais alto é ter deixado mais para
            trás.
          </p>
          <p className="note">
            A matrícula garantida <strong>não</strong> infla a primeira rodada: o calouro está fora
            do recorte, então o número é só o que o mecanismo alocou a quem disputou.
          </p>
          <div className="chart-grid">{saturation.map(chartFor)}</div>
        </section>
      )}

      {sweep && sweep.points.length > 1 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>Dependência da dispersão da preferência</h2>
            <p>
              A mesma comparação em vários <em>σ</em>, com {sweep.runs}{" "}
              {sweep.runs === 1 ? "execução" : "execuções"} por ponto — aqui se lê a{" "}
              <strong>forma da curva</strong>, não a significância de um ponto, que é o que os
              boxplots acima respondem no <em>σ</em> canônico, marcado no eixo
            </p>
          </header>
          <p className="note">
            <em>σ</em> é o desvio da log-normal de onde sai a utilidade: à{" "}
            <strong>esquerda</strong> o aluno é quase indiferente entre as disciplinas e à{" "}
            <strong>direita</strong> ele quer uma ou duas e despreza o resto.
          </p>
          <p className="note">
            O que esta seção mostra é a hipótese do trabalho: a linha da{" "}
            <strong>ordenação por CR é plana</strong> — concentrar a preferência da população não
            muda nada para um mecanismo que não enxerga intensidade —, enquanto a do leilão sobe.
            O vão entre elas <em>é</em> o quanto de intensidade há para captar. Em troca, o painel
            de <strong>formandos</strong> cai na mesma direção: é a taxa de câmbio entre satisfação
            e diplomas.
          </p>
          <div className="chart-grid">{[...METRICS, GRADUATES].map(sweepChartFor)}</div>
        </section>
      )}

      {sweep && sweep.points.length > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>Como a utilidade se reparte em cada σ</h2>
            <p>
              O gráfico da <strong>causa</strong>, ao lado dos da consequência: um histograma por
              ponto da varredura, mostrando como a preferência de um aluno se distribui entre as
              disciplinas que ele tem diante de si
            </p>
          </header>
          <p className="note">
            Cada linha (aluno, período) é reescalada ao <strong>próprio</strong> mínimo e máximo e
            dividida em {sweep.points[0].distribution.length} faixas de mesma largura; a altura é a
            fração de utilidades que cai em cada faixa, e elas somam 1. Utilidade zero não entra —
            ela marca o inelegível, não uma preferência fraca.
          </p>
          <p className="note">
            O eixo horizontal traz as <strong>divisas</strong> das faixas. Como a escala é por
            linha, ele não é o valor da utilidade: <strong>0</strong> é a disciplina que aquele
            aluno <em>menos</em> quer no período e <strong>1</strong> é a que ele <em>mais</em>{" "}
            quer, com os valores no meio dizendo onde entre as duas cada disciplina caiu. Massa
            empilhada à esquerda é um aluno que quer uma coisa e despreza o resto; massa espalhada
            é um aluno que diferencia pouco.
          </p>
          <p className="note">
            A escala é <strong>por linha</strong>, e não do menor ao maior valor da matriz inteira,
            porque global degenera: um único extremo define o intervalo e, de σ = 1 em diante, 94%
            dos valores caem na primeira faixa — todos os gráficos sairiam iguais e nenhum
            descreveria um aluno. A última faixa guarda sempre o máximo da linha, então ela nunca
            é vazia: num conjunto de <em>n</em> disciplinas ela vale pelo menos 1/<em>n</em>.
          </p>
          <div className="chart-grid">
            {sweep.points.map((point) => (
              <Histogram
                key={`hist-${point.sigma}`}
                title={`σ = ${formatSigma(point.sigma)}`}
                hint={
                  Math.abs(point.sigma - sweep.canonical) < 1e-9
                    ? "o σ canônico do cenário"
                    : undefined
                }
                fractions={point.distribution}
              />
            ))}
          </div>
        </section>
      )}

      {scenarioHistograms.length > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>As distribuições do cenário</h2>
            <p>
              De onde vieram os números: as duas matrizes sorteadas na inicialização, cada uma como
              a fração de valores que cai em cada faixa
            </p>
          </header>
          <p className="note">
            As <strong>notas</strong> são as de primeira tentativa, sobre [0, 10] — é a normal do
            cenário já truncada e arredondada, e o truncamento empilha massa nas pontas sempre que
            a média estiver perto delas, o que não se lê dos parâmetros. A recursada fica de fora
            porque ela desloca a média: misturar as tentativas somaria distribuições diferentes, e
            quantas recursadas acontecem é resultado, não entrada.
          </p>
          <p className="note">
            Nas <strong>utilidades</strong>, cada linha (aluno, período) é reescalada ao{" "}
            <strong>próprio</strong> mínimo e máximo, então o eixo não é o valor da utilidade:{" "}
            <strong>0</strong> é a disciplina que aquele aluno menos quer no período e{" "}
            <strong>1</strong> é a que ele mais quer. Massa à esquerda é um aluno que quer uma
            coisa e despreza o resto; massa espalhada é um aluno que diferencia pouco.
          </p>
          <div className="chart-grid">{scenarioHistograms}</div>
        </section>
      )}

      <div className="panel">
        <h2>O que o retorno de créditos muda</h2>
        <p className="note">
          Os dois braços do leilão rodam o <strong>mesmo cenário com a mesma seed</strong> e
          diferem em uma única coisa: a política f<sub>γ</sub>. A diferença entre eles é, portanto,
          o efeito do retorno — isolado. A coluna <strong>subiu</strong> é a contagem pareada, e é
          descritiva: conta em quantas seeds a métrica ficou maior com retorno, sem dizer se maior
          é bom. Ao lado, a mediana da linha de base, para localizar os dois no caminho entre
          ignorar o histórico e deixá-lo decidir tudo.
        </p>
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

      <div className="panel">
        <h2>Resumo das distribuições</h2>
        <p className="note">
          O mesmo conteúdo dos gráficos em números. A <strong>diferença</strong> e as{" "}
          <strong>seeds a favor</strong> são medidas contra a linha de base por CR: a diferença
          entre as medianas, e em quantas das {result.runs} populações aquele modelo saiu{" "}
          <em>melhor</em> que ela — maior em ψ̄ e φ, menor no tempo de formatura. Em λ e nas rodadas
          as duas colunas vêm vazias de propósito: elas descrevem, não pontuam, e qual lado é
          melhor ali depende do que se está perguntando. As duas leituras não são equivalentes:
          uma diferença pequena de medianas com quase todas as seeds a favor é um efeito
          consistente e pequeno, e é coisa diferente de um empate.
        </p>
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
        <h2>Execução a execução</h2>
        <p className="note">
          O pareamento à vista: cada linha é uma seed, e os três valores de cada coluna são a mesma
          população sob regras diferentes, na ordem da legenda. <strong>Formados</strong> está aqui
          porque o tempo de formatura não se lê sem ele — se um modelo forma bem menos gente, o
          tempo dele é a média de um grupo selecionado. "Períodos" é quantos a simulação publicou:
          se os braços divergirem aí, a população se esvaziou em momentos diferentes e as médias
          cobrem horizontes distintos. As rodadas ficam de fora desta tabela, que já tem três
          valores por célula; elas estão nas duas de cima.
        </p>
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
        <p className="note">
          Em cada célula, na ordem:{" "}
          {COMPARISON_ARMS.map((arm, i) => (
            <span key={arm.key}>
              {i > 0 && " / "}
              <span className="swatch" style={{ background: colors[arm.label] }} /> {arm.label}
            </span>
          ))}
          .
        </p>
      </div>
    </div>
  );
}
