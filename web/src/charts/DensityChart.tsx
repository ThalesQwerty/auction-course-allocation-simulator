/** A curva de densidade — a forma que um parâmetro produz.
 *
 * Diferente do histograma, aqui não há dado contado: a tela de configuração
 * desenha a distribuição que os parâmetros **implicam**, antes de qualquer
 * execução. Barras sugeririam contagem onde não há nenhuma; a área sob a
 * curva é o que diz "a massa está aqui".
 *
 * O que o eixo vertical mede é **densidade**: massa por unidade do eixo x,
 * com área 1 sob a curva. Daí ela passar de 1 quando o eixo x é estreito — a
 * altura de uma densidade não se lê sozinha, e é por isso que o tooltip
 * mostra também o percentil.
 */
import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DensityPoint } from "../equations";
import { inkFor, soloColor, usePrefersDark } from "./theme";

/** Corte que parte a curva em duas cores — a nota mínima. Antes dele a área é
 * de quem reprova, depois é de quem aprova, e o encontro das duas *é* o
 * corte: não há faixa dividida, porque não há faixa. */
export interface DensitySplit {
  at: number;
  below: string;
  above: string;
  labels: [string, string];
}

const HEIGHT = 150;

/** Casas decimais de uma régua: o menor número que ainda distingue marcas a
 * um décimo do intervalo. */
const digitsFor = (span: number) => Math.max(0, Math.ceil(-Math.log10(span / 10)));

const fixed = (digits: number) => (value: number) =>
  value.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

export function DensityChart({
  title,
  points,
  domain,
  split,
  controls,
  footer,
  id,
}: {
  title: string;
  points: DensityPoint[];
  domain: [number, number];
  split?: DensitySplit;
  controls?: ReactNode;
  /** Os números que a curva não mostra sozinha — o valor mais provável e, nas
   * notas, a aprovação. Vão ao pé do card, e não no título, porque são
   * leitura do desenho e não identificação dele. */
  footer?: ReactNode;
  /** Identificador do gradiente no SVG — dois gráficos na mesma página não
   * podem dividir o mesmo `id`. */
  id: string;
}) {
  const dark = usePrefersDark();
  const ink = inkFor(dark);
  const solo = soloColor(dark);
  const [low, high] = domain;
  const span = high - low || 1;

  // Onde o corte cai, em fração da largura. As duas paradas do gradiente
  // ficam no mesmo ponto, de modo que a cor vira de uma vez — é uma divisa,
  // não um degradê.
  const cut = Math.min(1, Math.max(0, (split ? split.at - low : 0) / span));

  const digits = digitsFor(span);
  const tick = (value: number) =>
    value.toLocaleString("pt-BR", { maximumFractionDigits: digits });
  // O mouse cai **entre** as marcas do eixo, então ele precisa de uma casa a
  // mais: no eixo das notas as marcas são inteiras, e a nota não é.
  const exact = fixed(digits + 1);

  // Topo da régua: o primeiro inteiro acima do pico. O piso é 1, de modo que
  // uma curva baixa — a das notas, cujo pico é 0,21 — se leia como baixa, em
  // vez de a régua se fechar em torno dela.
  const tallest = points.reduce((max, point) => Math.max(max, point.y), 0);
  const ceiling = Math.floor(tallest) + 1;
  const heightDigits = ceiling >= 10 ? 0 : 2;

  return (
    <figure className="chart-card">
      <figcaption>
        <h3>{title}</h3>
      </figcaption>

      {controls && <div className="chart-controls">{controls}</div>}

      {split && (
        <div className="legend">
          {[
            { color: split.below, label: split.labels[0] },
            { color: split.above, label: split.labels[1] },
          ].map((item) => (
            <span className="legend-item" key={item.label}>
              <span className="swatch" style={{ background: item.color }} />
              {item.label}
            </span>
          ))}
        </div>
      )}

      <ResponsiveContainer width="100%" height={HEIGHT}>
        <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="1" y2="0">
              <stop offset={cut} stopColor={split ? split.below : solo} />
              <stop offset={cut} stopColor={split ? split.above : solo} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="x"
            type="number"
            domain={[low, high]}
            tickCount={6}
            tickFormatter={tick}
            tick={{ fill: ink.muted, fontSize: 10 }}
            tickLine={false}
            stroke={ink.axis}
          />
          <YAxis
            domain={[0, ceiling]}
            ticks={[0, 0.25, 0.5, 0.75, 1].map((part) => part * ceiling)}
            tick={{ fill: ink.muted, fontSize: 10 }}
            tickLine={false}
            stroke={ink.axis}
            width={40}
            tickFormatter={fixed(heightDigits)}
          />
          <Tooltip
            cursor={{ stroke: ink.axis }}
            content={
              <CumulativeTip
                format={exact}
                height={fixed(heightDigits + 1)}
                split={split}
                dark={dark}
              />
            }
          />
          <Area
            type="monotone"
            dataKey="y"
            stroke={`url(#${id})`}
            strokeWidth={2}
            fill={`url(#${id})`}
            fillOpacity={0.28}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>

      {footer && <p className="chart-footer">{footer}</p>}
    </figure>
  );
}

/** No mouse: o ponto da curva e o **percentil** dele — a massa acumulada até
 * ali, que é a única leitura de probabilidade que uma densidade dá num ponto
 * só. */
function CumulativeTip({
  active,
  payload,
  label,
  format,
  height,
  split,
  dark,
}: {
  active?: boolean;
  payload?: { payload?: { y?: number; cum?: number } }[];
  label?: number;
  format: (value: number) => string;
  height: (value: number) => string;
  split?: DensitySplit;
  dark: boolean;
}) {
  const point = payload?.[0]?.payload;
  if (!active || point?.cum === undefined || point.y === undefined || label === undefined) {
    return null;
  }
  const ink = inkFor(dark).secondary;
  // De que lado do corte o ponto está — a mesma comparação que o motor faz
  // com a nota mínima, inclusive no empate: a nota igual a n_min aprova.
  const side = split
    ? label >= split.at
      ? { label: split.labels[1], color: split.above }
      : { label: split.labels[0], color: split.below }
    : null;

  return (
    <div className="tooltip">
      <div className="tooltip-title">
        <span>{format(label)}</span>
        {side && <span style={{ color: side.color }}>{side.label}</span>}
      </div>
      <div className="tooltip-row">
        <span className="tooltip-label">Densidade</span>
        <span className="tooltip-value" style={{ color: ink }}>
          {height(point.y)}
        </span>
      </div>
      <div className="tooltip-row">
        <span className="tooltip-label">Percentil</span>
        <span className="tooltip-value" style={{ color: ink }}>
          {(point.cum * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%
        </span>
      </div>
    </div>
  );
}
