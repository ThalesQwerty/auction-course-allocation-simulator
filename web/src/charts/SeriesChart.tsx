/** O gráfico de séries — o perfil de uma métrica ao longo do horizonte.
 *
 * É a outra leitura do mesmo material do boxplot, e a diferença está no eixo
 * horizontal. Lá ele é categórico: cada caixa é um modelo, e o que se lê é a
 * **distribuição** de uma média entre as execuções. Aqui ele é **ordenado** —
 * o período —, e o que se lê é a trajetória que aquela média resume. Por isso
 * a linha é lícita aqui e não seria sobre as seeds: entre o período 5 e o 6 há
 * caminho; entre a seed 5 e a 6 não há nada, e uma linha ali desenharia uma
 * tendência que é só a ordem do sorteio.
 *
 * **A linha é a mediana entre as execuções, e a faixa é o intervalo
 * interquartil.** A mediana, e não a média, porque é o número que as caixas e
 * as tabelas já usam — duas estatísticas para a mesma grandeza na mesma tela
 * obrigariam quem lê a reconciliá-las. A faixa não é enfeite: sem ela, linhas
 * lisas convidam a ler um vão de 0,01 como real quando as execuções se
 * espalham por 0,08 — e os quartis exatos ficam no tooltip.
 *
 * **A legenda alterna.** Com quatro braços sobrepostos, isolar dois é o que
 * torna um vão legível — e é assim que a figura vai para o texto.
 */
import { useMemo, useState } from "react";
import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { boxStats, paddedScale } from "../equations";
import type { BoxStats } from "../equations";
import { formatRatio } from "./format";
import { inkFor, usePrefersDark } from "./theme";

const HEIGHT = 200;

/** Folga menor que a do boxplot, e pelo mesmo motivo que ele tem a dele: a
 * faixa é a metade central da amostra, não os extremos. Só vale para métrica
 * sem contradomínio — ver `paddedScale`. */
const PADDING = 0.1;

export interface SeriesPoint {
  x: number;
  y: number;
}

export interface SeriesGroup {
  label: string;
  /** Uma amostra por execução. Cada uma traz os próprios `x`: as seeds não
   * precisam cobrir o mesmo intervalo, e na cauda do horizonte de fato não
   * cobrem — quem esvaziou antes para de publicar período. */
  samples: SeriesPoint[][];
}

/** O que foi medido num ponto do eixo: os cinco números entre as execuções que
 * chegaram até ali. São os mesmos de `boxStats` de propósito — a linha é a
 * mediana de uma caixa que não se desenha, e as duas leituras da tela não
 * podem sair de estatísticas diferentes. */
interface Summary {
  stats: BoxStats;
}

const summarize = (values: number[]): Summary | null => {
  const stats = boxStats(values);
  return stats ? { stats } : null;
};

export function SeriesChart({
  title,
  groups,
  colors,
  format = formatRatio,
  bounds,
  zeroLine = false,
  runs,
  xLabel = (x) => String(x),
}: {
  title: string;
  groups: SeriesGroup[];
  colors: Record<string, string>;
  format?: (value: number) => string;
  /** O contradomínio da métrica. Com os dois limites finitos, **a régua é
   * ele** — a série se desenha na escala da grandeza, e não na da amostra. */
  bounds?: [number, number];
  /** Marca o zero quando o sinal da métrica é o que se lê (λ). */
  zeroLine?: boolean;
  /** Quantas execuções cada braço tem. Serve ao tooltip, para avisar quando o
   * ponto foi medido sobre menos que todas — na cauda do horizonte parte das
   * seeds já esvaziou, e ali a amostra não é a mesma do começo do eixo. */
  runs: number;
  xLabel?: (x: number) => string;
}) {
  const dark = usePrefersDark();
  const ink = inkFor(dark);
  const [hidden, setHidden] = useState<Record<string, boolean>>({});

  /** Memoizado porque dele saem a tabela e a régua: alternar a legenda não
   * muda `groups`, e sem isso cada clique recalcularia os quartis de todas as
   * execuções. */
  const visible = useMemo(
    () => groups.filter((group) => !hidden[group.label]),
    [groups, hidden]
  );

  /** O eixo: a união dos períodos publicados, em ordem. */
  const xs = useMemo(() => {
    const seen = new Set<number>();
    groups.forEach((group) =>
      group.samples.forEach((sample) => sample.forEach((point) => seen.add(point.x)))
    );
    return [...seen].sort((a, b) => a - b);
  }, [groups]);

  /** Por braço e por ponto do eixo, o resumo entre as execuções. */
  const summaries = useMemo(() => {
    const table: Record<string, Map<number, Summary>> = {};
    groups.forEach((group) => {
      const byX = new Map<number, number[]>();
      group.samples.forEach((sample) =>
        sample.forEach((point) => {
          const bucket = byX.get(point.x);
          if (bucket) bucket.push(point.y);
          else byX.set(point.x, [point.y]);
        })
      );
      const summarized = new Map<number, Summary>();
      byX.forEach((values, x) => {
        const summary = summarize(values);
        if (summary) summarized.set(x, summary);
      });
      table[group.label] = summarized;
    });
    return table;
  }, [groups]);

  const data = useMemo(
    () =>
      xs.map((x) => {
        const row: Record<string, number | [number, number] | null> = { x };
        visible.forEach((group) => {
          const summary = summaries[group.label]?.get(x);
          row[group.label] = summary ? summary.stats.median : null;
          row[bandKey(group.label)] = summary
            ? [summary.stats.q1, summary.stats.q3]
            : null;
        });
        return row;
      }),
    [xs, visible, summaries]
  );

  /** A régua sai dos quartis desenhados — mas só quando a métrica não tem
   * contradomínio; tendo, é ele. */
  const spread = visible.flatMap((group) =>
    [...(summaries[group.label]?.values() ?? [])].flatMap((summary) => [
      summary.stats.q1,
      summary.stats.q3,
    ])
  );
  const scale = paddedScale(spread, { bounds, zeroLine, padding: PADDING });

  return (
    <figure className="chart-card">
      <figcaption>
        <h3>{title}</h3>
      </figcaption>

      <div className="legend">
        {groups.map((group) => (
          <button
            type="button"
            className={`legend-item legend-toggle${hidden[group.label] ? " off" : ""}`}
            key={group.label}
            aria-pressed={!hidden[group.label]}
            onClick={() =>
              setHidden((current) => ({
                ...current,
                [group.label]: !current[group.label],
              }))
            }
          >
            <span className="swatch" style={{ background: colors[group.label] }} />
            {group.label}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={HEIGHT}>
        <ComposedChart data={data} margin={{ top: 8, right: 10, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="x"
            type="number"
            domain={["dataMin", "dataMax"]}
            allowDecimals={false}
            tick={{ fill: ink.muted, fontSize: 10 }}
            tickLine={false}
            stroke={ink.axis}
          />
          <YAxis
            domain={[scale.from, scale.to]}
            ticks={scale.ticks}
            tickFormatter={format}
            tick={{ fill: ink.muted, fontSize: 10 }}
            tickLine={false}
            stroke={ink.axis}
            width={48}
          />
          {zeroLine && scale.from < 0 && scale.to > 0 && (
            <ReferenceLine y={0} stroke={ink.axis} />
          )}
          <Tooltip
            cursor={{ stroke: ink.axis }}
            content={
              <PeriodTip
                groups={visible}
                summaries={summaries}
                colors={colors}
                format={format}
                runs={runs}
                dark={dark}
                xLabel={xLabel}
              />
            }
          />
          {/* As faixas primeiro, para as medianas ficarem por cima de todas —
              senão a linha de um braço some sob a faixa do vizinho. */}
          {visible.map((group) => (
            <Area
              key={bandKey(group.label)}
              dataKey={bandKey(group.label)}
              stroke="none"
              fill={colors[group.label]}
              fillOpacity={0.12}
              isAnimationActive={false}
              connectNulls
              activeDot={false}
            />
          ))}
          {visible.map((group) => (
            <Line
              key={group.label}
              type="monotone"
              dataKey={group.label}
              stroke={colors[group.label]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </figure>
  );
}

/** A chave da faixa de um braço na tabela que o recharts lê. Sai do rótulo
 * para a série e a faixa andarem juntas sem uma segunda estrutura. */
const bandKey = (label: string) => `${label} (faixa)`;

/** No mouse: um período, e o que cada braço mediu nele.
 *
 * Em ordem decrescente de mediana, como no `SeriesTip` das outras séries — com
 * várias linhas no mesmo ponto, a ordem da legenda obrigaria a procurar. O `n`
 * só aparece quando o ponto foi medido sobre menos execuções que o total: é o
 * aviso de que ali a amostra mudou. */
function PeriodTip({
  active,
  label,
  groups,
  summaries,
  colors,
  format,
  runs,
  dark,
  xLabel,
}: {
  active?: boolean;
  label?: number;
  groups: SeriesGroup[];
  summaries: Record<string, Map<number, Summary>>;
  colors: Record<string, string>;
  format: (value: number) => string;
  runs: number;
  dark: boolean;
  xLabel: (x: number) => string;
}) {
  if (!active || label === undefined) return null;
  const ink = inkFor(dark);
  const rows = groups
    .map((group) => ({ group, summary: summaries[group.label]?.get(label) }))
    .filter((row): row is { group: SeriesGroup; summary: Summary } => !!row.summary)
    .sort((a, b) => b.summary.stats.median - a.summary.stats.median);
  if (!rows.length) return null;

  return (
    <div className="tooltip">
      <div className="tooltip-title">{xLabel(label)}</div>
      {rows.map(({ group, summary }) => (
        <div className="tooltip-row" key={group.label}>
          <span className="swatch" style={{ background: colors[group.label] }} />
          <span className="tooltip-label">{group.label}</span>
          <span className="tooltip-value" style={{ color: ink.secondary }}>
            {format(summary.stats.median)}
            <span className="tooltip-aside">
              {` ${format(summary.stats.q1)}–${format(summary.stats.q3)}`}
              {summary.stats.n < runs ? ` · n=${summary.stats.n}` : ""}
            </span>
          </span>
        </div>
      ))}
      <div className="tooltip-foot">mediana · intervalo interquartil</div>
    </div>
  );
}
