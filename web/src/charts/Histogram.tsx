/** Histograma de uma distribuição já contada: **uma** série, então sem
 * legenda — o título diz de quem é a barra — e matiz única, porque as barras
 * são faixas da mesma grandeza e não categorias diferentes.
 *
 * O eixo x traz as **divisas** das faixas, e não a contagem de 1 a n: a
 * grandeza é contínua e o que importa é onde a faixa começa e termina. O eixo
 * y vai de 0 a 1 fixo, porque estes gráficos existem para serem comparados
 * entre si, e um eixo que se ajusta a cada um faria distribuições diferentes
 * parecerem iguais.
 *
 * A régua de divisas é desenhada em HTML, e não pelo Recharts, porque o eixo
 * categórico dele põe rótulo no **centro** da barra e o que se quer aqui é o
 * valor **entre** barras.
 */
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

/** Teto de casas decimais das divisas. Além disso a régua fica ilegível, e
 * uma grade com tantas disciplinas assim não é cenário real. */
const MAX_DIGITS = 6;

const SERIES = "fração";

/** As casas decimais que a régua precisa: o menor número que ainda escreve
 * todas as divisas **distintas**.
 *
 * Em [0, 10] isso dá zero; em [0, 1], uma; num eixo que vai até 0,043 — a
 * fração de utilidade de uma grade de 60 disciplinas — dá três, que é o que
 * impede a régua de sair "0 0 0 0". Arredondar o rótulo é normal numa régua;
 * repetir dois rótulos diferentes não é. */
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
  /** Uma fração por faixa, em ordem, somando 1. */
  fractions: number[];
  format?: (value: number) => string;
  /** O intervalo que as faixas cobrem, para rotular as divisas. Utilidade
   * reescalada por linha vai de 0 a 1; nota vai de 0 a 10. */
  domain?: [number, number];
  /** Uma cor por faixa, quando a cor diz um **estado** e não a identidade da
   * série. Ausente, todas saem na matiz única. */
  binColors?: string[];
  /** Obrigatória junto de `binColors`: cor de estado nunca carrega
   * significado sozinha. */
  legend?: { color: string; label: string }[];
  /** Campos que configuram **este gráfico**, e não a simulação. */
  controls?: ReactNode;
}) {
  const dark = usePrefersDark();
  const ink = inkFor(dark);
  const fill = soloColor(dark);

  // n faixas têm n + 1 divisas, igualmente espaçadas no domínio.
  const [low, high] = domain;
  const edges = Array.from(
    { length: fractions.length + 1 },
    (_, i) => low + ((high - low) * i) / fractions.length
  );
  const digits = digitsFor(edges);

  // As pontas saem sem casas decimais — é o 0 e o 1 do domínio, e "0,10" no
  // lugar de "1" se lê como outro número.
  const edgeLabel = (index: number) =>
    index === 0 || index === fractions.length
      ? edges[index].toLocaleString("pt-BR", { maximumFractionDigits: digits })
      : edges[index].toLocaleString("pt-BR", {
          minimumFractionDigits: digits,
          maximumFractionDigits: digits,
        });

  // Separador do par: vírgula onde ela está livre, ponto e vírgula onde a
  // vírgula já é a decimal — "[0,1, 0,2)" se lê como quatro números.
  const separator = digits > 0 ? "; " : ", ";

  // A faixa se identifica pelo intervalo que cobre, não pela posição: "[7, 8)"
  // é o que se lê na régua, e "3" não quer dizer nada. É fechada à esquerda e
  // aberta à direita, **menos a última**, fechada dos dois lados — é nela que
  // o máximo do domínio cai, por convenção dos dois histogramas do motor. Daí
  // a nota 10 contar como aprovação e não cair fora do gráfico.
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
