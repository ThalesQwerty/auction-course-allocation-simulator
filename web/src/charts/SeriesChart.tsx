/** O gráfico de séries — uma métrica ao longo do horizonte, período a período.
 *
 * **A linha é a mediana entre as simulações, e a faixa é o intervalo
 * interquartil.** A redução já vem feita da API (`GroupBands`): aqui só se
 * desenha. A faixa não é enfeite: sem ela, linhas lisas convidam a ler um vão
 * de 0,01 como real quando as simulações se espalham por 0,08.
 *
 * **Duas codificações, uma por dimensão.** A cor é o grupo do recorte (um
 * perfil, uma coorte); o traçado é o modelo (contínuo, tracejado). A legenda
 * alterna cada uma por conta própria: esconder um traçado deixa todas as cores
 * de um modelo só, e esconder cores isola grupos nos dois modelos.
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

import { paddedScale } from "../equations";
import { formatRatio } from "./format";
import { inkFor, usePrefersDark } from "./theme";

const HEIGHT = 220;

/** Folga da régua quando a métrica não tem contradomínio — ver `paddedScale`. */
const PADDING = 0.1;

/** Um período de uma linha: a faixa entre as seeds e quantas a mediram. */
export interface BandPoint {
  x: number;
  q1: number;
  median: number;
  q3: number;
  n: number;
}

/** Uma linha do gráfico: um grupo do recorte sob um modelo. */
export interface SeriesLine {
  group: string;
  arm: string;
  points: BandPoint[];
}

/** Um grupo do recorte, com a cor que o cenário lhe deu. */
export interface SeriesGroupStyle {
  key: string;
  label: string;
  color: string;
}

/** Um modelo, com o traçado da linha dele (`strokeDasharray`; vazio é
 * contínuo). */
export interface SeriesArmStyle {
  key: string;
  label: string;
  dash: string;
}

/** O traço de amostra de um modelo, para a legenda e o tooltip. */
export function LineSample({ dash, color }: { dash: string; color: string }) {
  return (
    <svg className="line-sample" width="22" height="10" aria-hidden="true">
      <line
        x1="1"
        y1="5"
        x2="21"
        y2="5"
        stroke={color}
        strokeWidth="2"
        strokeDasharray={dash || undefined}
        strokeLinecap="round"
      />
    </svg>
  );
}

const lineKey = (line: { arm: string; group: string }) => `${line.arm}|${line.group}`;
const bandKey = (key: string) => `${key} (faixa)`;

export function SeriesChart({
  title,
  accent,
  lines,
  groups,
  arms,
  format = formatRatio,
  bounds,
  zeroLine = false,
  runs,
  xLabel = (x) => String(x),
}: {
  title: string;
  /** Cor do quadrado ao lado do título, quando o que o gráfico mostra é um
   * **estado** e não uma grandeza — os seis de uma solicitação. */
  accent?: string;
  lines: SeriesLine[];
  groups: SeriesGroupStyle[];
  arms: SeriesArmStyle[];
  format?: (value: number) => string;
  /** O contradomínio da métrica. Com os dois limites finitos, **a régua é
   * ele** — a série se desenha na escala da grandeza, e não na da amostra. */
  bounds?: [number, number];
  /** Marca o zero quando o sinal da métrica é o que se lê (λ). */
  zeroLine?: boolean;
  /** Quantas simulações cada modelo tem. O tooltip avisa quando o ponto foi
   * medido sobre menos que todas. */
  runs: number;
  xLabel?: (x: number) => string;
}) {
  const dark = usePrefersDark();
  const ink = inkFor(dark);
  const [hiddenGroups, setHiddenGroups] = useState<Record<string, boolean>>({});
  const [hiddenArms, setHiddenArms] = useState<Record<string, boolean>>({});

  const colorOf = useMemo(
    () => Object.fromEntries(groups.map((g) => [g.key, g.color])),
    [groups]
  );
  const dashOf = useMemo(
    () => Object.fromEntries(arms.map((a) => [a.key, a.dash])),
    [arms]
  );
  const groupLabel = useMemo(
    () => Object.fromEntries(groups.map((g) => [g.key, g.label])),
    [groups]
  );
  const armLabel = useMemo(
    () => Object.fromEntries(arms.map((a) => [a.key, a.label])),
    [arms]
  );

  const visible = useMemo(
    () => lines.filter((line) => !hiddenGroups[line.group] && !hiddenArms[line.arm]),
    [lines, hiddenGroups, hiddenArms]
  );

  /** Por linha, o ponto de cada período — o que o tooltip consulta. */
  const byX = useMemo(() => {
    const table = new Map<string, Map<number, BandPoint>>();
    lines.forEach((line) =>
      table.set(lineKey(line), new Map(line.points.map((p) => [p.x, p])))
    );
    return table;
  }, [lines]);

  /** O eixo: a união dos períodos publicados, em ordem. */
  const xs = useMemo(() => {
    const seen = new Set<number>();
    lines.forEach((line) => line.points.forEach((p) => seen.add(p.x)));
    return [...seen].sort((a, b) => a - b);
  }, [lines]);

  const data = useMemo(
    () =>
      xs.map((x) => {
        const row: Record<string, number | [number, number] | null> = { x };
        visible.forEach((line) => {
          const key = lineKey(line);
          const point = byX.get(key)?.get(x);
          row[key] = point ? point.median : null;
          row[bandKey(key)] = point ? [point.q1, point.q3] : null;
        });
        return row;
      }),
    [xs, visible, byX]
  );

  const spread = visible.flatMap((line) => line.points.flatMap((p) => [p.q1, p.q3]));
  const scale = paddedScale(spread, { bounds, zeroLine, padding: PADDING });
  // Com muitas linhas as faixas se somam e viram névoa; mais leves, elas
  // continuam dizendo onde a amostra se espalha sem cobrir as medianas.
  const bandOpacity = visible.length > 4 ? 0.05 : 0.12;

  const toggle =
    (set: typeof setHiddenGroups, key: string) => () =>
      set((current) => ({ ...current, [key]: !current[key] }));

  return (
    <figure className="chart-card">
      <figcaption>
        <h3>
          {accent && <span className="swatch" style={{ background: accent }} />}
          {title}
        </h3>
      </figcaption>

      <div className="legend">
        {groups.length > 1 &&
          groups.map((group) => (
            <button
              type="button"
              className={`legend-item legend-toggle${hiddenGroups[group.key] ? " off" : ""}`}
              key={`g-${group.key}`}
              aria-pressed={!hiddenGroups[group.key]}
              onClick={toggle(setHiddenGroups, group.key)}
            >
              <span className="swatch" style={{ background: group.color }} />
              {group.label}
            </button>
          ))}
        {groups.length > 1 && <span className="legend-divider" aria-hidden="true" />}
        {arms.map((arm) => (
          <button
            type="button"
            className={`legend-item legend-toggle${hiddenArms[arm.key] ? " off" : ""}`}
            key={`a-${arm.key}`}
            aria-pressed={!hiddenArms[arm.key]}
            onClick={toggle(setHiddenArms, arm.key)}
          >
            <LineSample
              dash={arm.dash}
              color={groups.length === 1 ? groups[0].color : ink.secondary}
            />
            {arm.label}
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
                lines={visible}
                byX={byX}
                colorOf={colorOf}
                dashOf={dashOf}
                groupLabel={groupLabel}
                armLabel={armLabel}
                showGroup={groups.length > 1}
                format={format}
                runs={runs}
                dark={dark}
                xLabel={xLabel}
              />
            }
          />
          {/* As faixas primeiro, para as medianas ficarem por cima de todas. */}
          {visible.map((line) => (
            <Area
              key={bandKey(lineKey(line))}
              dataKey={bandKey(lineKey(line))}
              stroke="none"
              fill={colorOf[line.group]}
              fillOpacity={bandOpacity}
              isAnimationActive={false}
              connectNulls
              activeDot={false}
            />
          ))}
          {visible.map((line) => (
            <Line
              key={lineKey(line)}
              type="monotone"
              dataKey={lineKey(line)}
              stroke={colorOf[line.group]}
              strokeDasharray={dashOf[line.arm] || undefined}
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

/** No mouse: um período, e o que cada linha mediu nele, em ordem decrescente
 * de mediana. O `n` só aparece quando o ponto foi medido sobre menos
 * simulações que o total. */
function PeriodTip({
  active,
  label,
  lines,
  byX,
  colorOf,
  dashOf,
  groupLabel,
  armLabel,
  showGroup,
  format,
  runs,
  dark,
  xLabel,
}: {
  active?: boolean;
  label?: number;
  lines: SeriesLine[];
  byX: Map<string, Map<number, BandPoint>>;
  colorOf: Record<string, string>;
  dashOf: Record<string, string>;
  groupLabel: Record<string, string>;
  armLabel: Record<string, string>;
  showGroup: boolean;
  format: (value: number) => string;
  runs: number;
  dark: boolean;
  xLabel: (x: number) => string;
}) {
  if (!active || label === undefined) return null;
  const ink = inkFor(dark);
  const rows = lines
    .map((line) => ({ line, point: byX.get(lineKey(line))?.get(label) }))
    .filter((row): row is { line: SeriesLine; point: BandPoint } => !!row.point)
    .sort((a, b) => b.point.median - a.point.median);
  if (!rows.length) return null;

  return (
    <div className="tooltip">
      <div className="tooltip-title">{xLabel(label)}</div>
      {rows.map(({ line, point }) => (
        <div className="tooltip-row" key={lineKey(line)}>
          <LineSample dash={dashOf[line.arm]} color={colorOf[line.group]} />
          <span className="tooltip-label">
            {showGroup
              ? `${groupLabel[line.group] ?? line.group} · ${armLabel[line.arm] ?? line.arm}`
              : armLabel[line.arm] ?? line.arm}
          </span>
          <span className="tooltip-value" style={{ color: ink.secondary }}>
            {format(point.median)}
            <span className="tooltip-aside">
              {` ${format(point.q1)}–${format(point.q3)}`}
              {point.n < runs ? ` · n=${point.n}` : ""}
            </span>
          </span>
        </div>
      ))}
      <div className="tooltip-foot">mediana · intervalo interquartil</div>
    </div>
  );
}
