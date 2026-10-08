import { useMemo } from "react";
import { BoxPlot, boxStats, categoricalColors, formatRatio, usePrefersDark } from "./charts";
import { describeComparison, formatRunDate, ComparisonRun } from "./history";
import { MECHANISMS } from "./types";
import type { ComparisonMetric, Mechanism, RunSummary } from "./types";

/** As cinco métricas principais — as que avaliam a *alocação*. Nada de
 * crédito: orçamento, preço e retorno não existem do lado da linha de base, e
 * comparar um mecanismo com o vazio não compara nada. E nenhum recorte por
 * geração ou perfil: aqui a pergunta é sobre o mecanismo, não sobre o que
 * acontece dentro de cada um. */
const METRICS: {
  key: ComparisonMetric;
  title: string;
  short: string;
  hint: string;
  /** Limites naturais da grandeza — o domínio é folgado em torno dos dados,
   * mas nunca passa daqui. */
  bounds: [number, number];
  zeroLine?: boolean;
}[] = [
  {
    key: "efficiency",
    title: "Eficiência de alocação (ψ̄)",
    short: "Eficiência (ψ̄)",
    hint: "Satisfação média dos alunos ativos — eq. (53). A utilidade é zero fora do conjunto elegível, então ψ é a fração do que o aluno podia cursar e conseguiu",
    bounds: [0, 1],
  },
  {
    key: "fairness",
    title: "Equidade (índice de Jain, φ)",
    short: "Equidade (φ)",
    hint: "1 = todos igualmente satisfeitos — eq. (55)",
    bounds: [0, 1],
  },
  {
    key: "correlation",
    title: "Correlação CR × satisfação (λ)",
    short: "Correlação (λ)",
    hint: "Positivo = quem tem CR maior se sai melhor — eq. (57). É a métrica em que os dois mecanismos se separam por construção: na linha de base o CR é literalmente o critério de alocação",
    bounds: [-1, 1],
    zeroLine: true,
  },
  {
    key: "occupancy",
    title: "Taxa de ocupação (θ)",
    short: "Ocupação (θ)",
    hint: "Fatia das vagas ofertadas que foi preenchida — eq. (54)",
    bounds: [0, 1],
  },
  {
    key: "semestralization",
    title: "Semestralização (σ̄)",
    short: "Semestralização (σ̄)",
    hint: "Carga aprovada ÷ máximo possível desde o ingresso; 1 = ninguém atrasado",
    bounds: [0, 1],
  },
];

const valuesOf = (runs: RunSummary[], metric: ComparisonMetric) =>
  runs.map((run) => run[metric]);

/** Sinal com sinal explícito: numa coluna de diferenças, "+0,04" e "−0,04"
 * se distinguem de relance e "0,04" não. */
const formatDelta = (value: number) =>
  `${value > 0 ? "+" : value < 0 ? "−" : ""}${formatRatio(Math.abs(value))}`;

export function Comparison({
  run,
  onReuseConfig,
}: {
  run: ComparisonRun;
  onReuseConfig: () => void;
}) {
  const dark = usePrefersDark();
  const result = run.result;

  const labels = MECHANISMS.map((m) => m.label);
  const colors = useMemo(() => categoricalColors(labels, dark), [dark, labels.join()]);
  const samples: Record<Mechanism, RunSummary[]> = {
    ranking: result.ranking,
    credits: result.credits,
  };

  // Estatística pareada: em quantas das N seeds o leilão ficou acima da linha
  // de base. Só faz sentido porque as duas listas compartilham a seed — é a
  // mesma população dos dois lados, e a comparação par a par não precisa
  // supor nada sobre a forma das distribuições.
  const favouring = (metric: ComparisonMetric) =>
    result.credits.filter((credits, i) => credits[metric] > result.ranking[i][metric]).length;

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
          {result.runs} execuções de cada mecanismo — {result.runs * 2} simulações
        </h2>
        <p className="note">
          As seeds vão de <strong>1 a {result.runs}</strong> e são <strong>pareadas</strong>: a
          i-ésima execução de um mecanismo e a do outro partem da mesma população, da mesma matriz
          de utilidades e da mesma matriz de notas. É a condição metodológica da Seção 7.3 — os
          dois lados recebem a mesma inicialização, e por isso a diferença entre eles é atribuível
          ao <strong>mecanismo</strong>, não ao sorteio nem às particularidades de um cenário.
        </p>
        <p className="note">
          Cada caixa é a distribuição da métrica sobre as {result.runs} execuções daquele
          mecanismo: a linha grossa é a <strong>mediana</strong>, a caixa é a metade central da
          amostra (1º ao 3º quartil), os bigodes vão até 1,5 IQR e o que sobra aparece como ponto
          solto. Uma execução vale um valor, e esse valor é a média dos períodos{" "}
          <strong>ponderada pelos alunos ativos</strong> — a simulação termina numa fase de
          drenagem, e sem o peso um período final de poucos alunos contaria tanto quanto um
          período cheio.
        </p>
        <p className="note">
          Só as métricas de alocação entram. Orçamento, preço e retorno de créditos não têm
          contraparte do lado da linha de base, e nenhum recorte por geração ou perfil aparece
          aqui: o que está em comparação é o mecanismo, não o que acontece dentro de cada um.
        </p>
      </div>

      <section className="chart-section">
        <header className="chart-section-head">
          <h2>Métricas principais</h2>
          <p>
            Caixas que não se tocam separam os mecanismos; caixas sobrepostas dizem que a
            diferença entre as medianas cabe dentro da variação entre populações
          </p>
        </header>
        <div className="chart-grid">
          {METRICS.map((metric) => (
            <BoxPlot
              key={metric.key}
              title={metric.title}
              hint={metric.hint}
              groups={MECHANISMS.map((mechanism) => ({
                label: mechanism.label,
                short: mechanism.short,
                values: valuesOf(samples[mechanism.value], metric.key),
              }))}
              colors={colors}
              bounds={metric.bounds}
              zeroLine={metric.zeroLine}
            />
          ))}
        </div>
      </section>

      <div className="panel">
        <h2>Resumo das distribuições</h2>
        <p className="note">
          O mesmo conteúdo dos gráficos em números. A <strong>diferença</strong> é a mediana do
          leilão menos a da linha de base, e <strong>seeds a favor</strong> é a contagem pareada:
          em quantas das {result.runs} populações o leilão ficou acima. As duas leituras não são
          equivalentes — uma diferença pequena de medianas com quase todas as seeds a favor é um
          efeito consistente e pequeno, e é coisa diferente de um empate.
        </p>
        <table>
          <thead>
            <tr>
              <th>Métrica</th>
              <th>Mecanismo</th>
              <th>Mín</th>
              <th>1º quartil</th>
              <th>Mediana</th>
              <th>3º quartil</th>
              <th>Máx</th>
              <th>Diferença</th>
              <th>Seeds a favor</th>
            </tr>
          </thead>
          <tbody>
            {METRICS.flatMap((metric) => {
              const stats = MECHANISMS.map((mechanism) => ({
                mechanism,
                box: boxStats(valuesOf(samples[mechanism.value], metric.key)),
              }));
              const baseline = stats.find((s) => s.mechanism.value === "ranking")?.box;
              const proposed = stats.find((s) => s.mechanism.value === "credits")?.box;
              return stats.map(({ mechanism, box }, index) => (
                <tr key={`${metric.key}-${mechanism.value}`}>
                  {/* O nome da métrica só na primeira das duas linhas: repetido
                      ele viraria ruído entre números que se comparam. */}
                  <td>{index === 0 ? metric.short : ""}</td>
                  <td>
                    <span className="swatch" style={{ background: colors[mechanism.label] }} />{" "}
                    {mechanism.label}
                  </td>
                  <td>{box ? formatRatio(box.min) : "—"}</td>
                  <td>{box ? formatRatio(box.q1) : "—"}</td>
                  <td>{box ? formatRatio(box.median) : "—"}</td>
                  <td>{box ? formatRatio(box.q3) : "—"}</td>
                  <td>{box ? formatRatio(box.max) : "—"}</td>
                  <td>
                    {mechanism.value === "credits" && baseline && proposed
                      ? formatDelta(proposed.median - baseline.median)
                      : ""}
                  </td>
                  <td>
                    {mechanism.value === "credits"
                      ? `${favouring(metric.key)}/${result.runs}`
                      : ""}
                  </td>
                </tr>
              ));
            })}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Execução a execução</h2>
        <p className="note">
          O pareamento à vista: cada linha é uma seed, e os dois valores de cada coluna são a
          mesma população sob regras diferentes. "Períodos" é quantos a simulação publicou — se os
          dois lados divergirem aí, a população se esvaziou em momentos diferentes, e as médias
          cobrem horizontes distintos.
        </p>
        <table>
          <thead>
            <tr>
              <th>Seed</th>
              <th>Períodos</th>
              {METRICS.map((metric) => (
                <th key={metric.key}>{metric.short}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.ranking.map((baseline, i) => {
              const proposed = result.credits[i];
              return (
                <tr key={baseline.seed}>
                  <td>{baseline.seed}</td>
                  <td>
                    {baseline.periods === proposed.periods
                      ? baseline.periods
                      : `${baseline.periods} / ${proposed.periods}`}
                  </td>
                  {METRICS.map((metric) => (
                    <td key={metric.key}>
                      {formatRatio(baseline[metric.key])} / {formatRatio(proposed[metric.key])}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="note">
          Em cada célula: <span style={{ color: colors[MECHANISMS[0].label] }}>■</span>{" "}
          {MECHANISMS[0].label} / <span style={{ color: colors[MECHANISMS[1].label] }}>■</span>{" "}
          {MECHANISMS[1].label}.
        </p>
      </div>
    </div>
  );
}
