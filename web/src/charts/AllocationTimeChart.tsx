/** O custo de **rodar** o mecanismo: quanto o alocador levou em cada rodada.
 *
 * É o único gráfico da tela que não mede o modelo. Os outros perguntam o que o
 * mecanismo produziu; este pergunta quanto custou produzi-lo, e por isso não
 * tem recorte por coorte nem por perfil — o resolvedor decide a rodada inteira
 * de uma vez, e não há parcela do tempo que pertença a um grupo de alunos.
 *
 * **A régua é logarítmica** porque os dois mecanismos ficam a ordens de
 * grandeza um do outro: numa régua linear a ordenação por CR encostaria no
 * zero e o gráfico viraria a linha do leilão sozinha. Em log a distância
 * vertical entre as linhas **é** a razão entre os tempos, que é a leitura que
 * interessa.
 *
 * Uma rodada que não alocou nada sai como buraco na linha, não como zero: zero
 * segundo se leria como "foi instantâneo", e o que houve foi não acontecer.
 */
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { SeriesTip } from "./SeriesTip";
import { categoricalColors, inkFor, usePrefersDark } from "./theme";

const LAYOUT = { height: 240, left: 52, right: 12 };

const ORDINALS = ["1ª", "2ª", "3ª", "4ª", "5ª", "6ª", "7ª", "8ª", "9ª", "10ª"];

/** Um mecanismo e a série de tempos dele: `seconds[p][r]` é a rodada r+1 do
 * período p+1. */
export interface AllocationTimeLine {
  key: string;
  label: string;
  /** `strokeDasharray`; vazio é contínuo. */
  dash: string;
  seconds: number[][];
}

/** Sempre em segundos, que é a unidade da régua. Duas casas **significativas**,
 * e não fixas: numa régua logarítmica os valores atravessam ordens de grandeza,
 * e casas fixas escreveriam "0,00" em tudo que está abaixo de um centésimo. */
export const formatSeconds = (value: number): string =>
  `${value.toLocaleString("pt-BR", { maximumSignificantDigits: 2 })} s`;

export function AllocationTimeChart({
  title,
  lines,
}: {
  title: string;
  lines: AllocationTimeLine[];
}) {
  const dark = usePrefersDark();
  const ink = inkFor(dark);
  const colors = categoricalColors(
    lines.map((line) => line.label),
    dark
  );

  const periods = Math.max(0, ...lines.map((line) => line.seconds.length));
  const rounds = Math.max(
    0,
    ...lines.flatMap((line) => line.seconds.map((period) => period.length))
  );
  if (periods === 0 || rounds === 0) return null;

  const data: Record<string, string | number | null>[] = [];
  for (let period = 0; period < periods; period++) {
    for (let round = 0; round < rounds; round++) {
      const row: Record<string, string | number | null> = {
        x: `${period + 1}º período · ${ORDINALS[round] ?? `${round + 1}ª`} rodada`,
      };
      for (const line of lines) {
        const value = line.seconds[period]?.[round];
        row[line.label] = value && value > 0 ? value : null;
      }
      data.push(row);
    }
  }

  return (
    <figure className="chart-card">
      <figcaption>
        <h3>{title}</h3>
      </figcaption>

      <div className="legend">
        {lines.map((line) => (
          <span className="legend-item" key={line.key}>
            <span className="swatch" style={{ background: colors[line.label] }} />
            {line.label}
          </span>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={LAYOUT.height}>
        <LineChart data={data} margin={{ top: 8, right: LAYOUT.right, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={ink.grid} vertical={false} />
          {/* A chave é o rótulo inteiro — é ele que o tooltip mostra —, mas a
              régua só escreve o período, na 1ª rodada dele: com |R| pontos por
              período, rotular todos sairia ilegível. */}
          <XAxis
            dataKey="x"
            interval={0}
            tickFormatter={(_value, index) =>
              index % rounds === 0 ? String(Math.floor(index / rounds) + 1) : ""
            }
            tick={{ fill: ink.muted, fontSize: 10 }}
            tickLine={false}
            stroke={ink.axis}
          />
          <YAxis
            scale="log"
            domain={["auto", "auto"]}
            allowDataOverflow
            tick={{ fill: ink.muted, fontSize: 10 }}
            tickLine={false}
            stroke={ink.axis}
            width={LAYOUT.left}
            tickFormatter={formatSeconds}
          />
          <Tooltip
            cursor={{ stroke: ink.grid }}
            content={
              <SeriesTip colors={colors} format={formatSeconds} dark={dark} />
            }
          />
          {lines.map((line) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.label}
              stroke={colors[line.label]}
              strokeDasharray={line.dash || undefined}
              strokeWidth={1.8}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </figure>
  );
}
