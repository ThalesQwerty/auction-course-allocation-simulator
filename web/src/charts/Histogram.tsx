/** Histograma de uma distribuição já contada: **uma** série, então sem legenda — o título diz de quem é a barra — e matiz única, porque as barras são faixas da mesma grandeza e não categorias diferentes */
import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatRatio } from "./format";
import { SeriesTip } from "./SeriesTip";
import { inkFor, soloColor, usePrefersDark } from "./theme";

const LAYOUT = { height: 150, left: 40, right: 12 };

/** Teto de casas decimais das divisas */
const MAX_DIGITS = 6;

const SERIES = "fração";

/** As casas decimais que a régua precisa: o menor número que ainda escreve todas as divisas **distintas** */
function digitsFor(edges: number[]): number {
  for (let digits = 0; digits < MAX_DIGITS; digits++) {
    if (new Set(edges.map((edge) => edge.toFixed(digits))).size === edges.length) {
      return digits;
    }
  }
  return MAX_DIGITS;
}

export function Histogram({
  title,
  fractions,
  format = formatRatio,
  domain = [0, 1],
  binColors,
  legend,
  controls,
}: {
  title: string;
  fractions: number[];
  format?: (value: number) => string;
   /** O intervalo que as faixas cobrem, para rotular as divisas */
  domain?: [number, number];
   /** Uma cor por faixa, quando a cor diz um **estado** e não a identidade da série */
  binColors?: string[];
   /** Obrigatória junto de `binColors`: cor de estado nunca carrega significado sozinha */
  legend?: { color: string; label: string }[];
  controls?: ReactNode;
}) {
  const dark = usePrefersDark();
  const ink = inkFor(dark);
  const fill = soloColor(dark);

  const [low, high] = domain;
  const edges = Array.from(
    { length: fractions.length + 1 },
    (_, i) => low + ((high - low) * i) / fractions.length
  );
  const digits = digitsFor(edges);

  const edgeLabel = (index: number) =>
    index === 0 || index === fractions.length
      ? edges[index].toLocaleString("pt-BR", { maximumFractionDigits: digits })
      : edges[index].toLocaleString("pt-BR", {
          minimumFractionDigits: digits,
          maximumFractionDigits: digits,
        });

  const separator = digits > 0 ? "; " : ", ";

  const data = fractions.map((value, index) => ({
    x: `[${edgeLabel(index)}${separator}${edgeLabel(index + 1)}${
      index === fractions.length - 1 ? "]" : ")"
    }`,
    [SERIES]: value,
  }));
  const colorOf = (label: string | undefined) => {
    const index = data.findIndex((row) => row.x === label);
    return index >= 0 ? binColors?.[index] : undefined;
  };

  return (
    <figure className="chart-card">
      <figcaption>
        <h3>{title}</h3>
      </figcaption>

      {controls && <div className="chart-controls">{controls}</div>}

      {legend && (
        <div className="legend">
          {legend.map((item) => (
            <span className="legend-item" key={item.label}>
              <span className="swatch" style={{ background: item.color }} />
              {item.label}
            </span>
          ))}
        </div>
      )}

      <ResponsiveContainer width="100%" height={LAYOUT.height}>
        <BarChart data={data} margin={{ top: 8, right: LAYOUT.right, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={ink.grid} vertical={false} />
          {/* Sem rótulo: quem rotula é a régua de divisas abaixo. */}
          <XAxis dataKey="x" tick={false} tickLine={false} height={6} stroke={ink.axis} />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: ink.muted, fontSize: 10 }}
            tickLine={false}
            stroke={ink.axis}
            width={LAYOUT.left}
            tickFormatter={format}
          />
          <Tooltip
            cursor={{ fill: ink.grid }}
            content={
              <SeriesTip
                colors={{ [SERIES]: fill }}
                format={format}
                dark={dark}
                fillFor={colorOf}
              />
            }
          />
          <Bar dataKey={SERIES} fill={fill} isAnimationActive={false} radius={[4, 4, 0, 0]}>
            {binColors &&
              data.map((row, index) => <Cell key={row.x} fill={binColors[index] ?? fill} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div
        className="histogram-edges"
        style={{ marginLeft: LAYOUT.left, marginRight: LAYOUT.right }}
      >
        {edges.map((edge, index) => (
          <span key={edge} style={{ left: `${(index / fractions.length) * 100}%` }}>
            {edgeLabel(index)}
          </span>
        ))}
      </div>
    </figure>
  );
}
