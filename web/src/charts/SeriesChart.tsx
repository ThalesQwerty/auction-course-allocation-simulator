/** O gráfico de séries — uma métrica ao longo do horizonte, período a período */
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

const PADDING = 0.1;

/** Um período de uma linha: a faixa entre as seeds e quantas a mediram */
export interface BandPoint {
  x: number;
  q1?: number;
  median: number;
  q3?: number;
  n: number;
}

const spanOf = (point: BandPoint): [number, number] | null =>
  point.q1 === undefined || point.q3 === undefined ? null : [point.q1, point.q3];

export interface SeriesLine {
  group: string;
  arm: string;
  points: BandPoint[];
}

export interface SeriesGroupStyle {
  key: string;
  label: string;
  color: string;
}

/** Um modelo, com o traçado da linha dele (`strokeDasharray`; vazio é contínuo) */
export interface SeriesArmStyle {
  key: string;
  label: string;
  dash: string;
}

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
  axisLabel,
  showCount = false,
  foot = "mediana · intervalo interquartil",
}: {
  title: string;
   /** Cor do quadrado ao lado do título, quando o que o gráfico mostra é um **estado** e não uma grandeza — os seis de uma solicitação */
  accent?: string;
  lines: SeriesLine[];
  groups: SeriesGroupStyle[];
  arms: SeriesArmStyle[];
  format?: (value: number) => string;
   /** O contradomínio da métrica */
  bounds?: [number, number];
  zeroLine?: boolean;
   /** Quantas simulações cada modelo tem */
  runs: number;
  xLabel?: (x: number) => string;
   /** O nome do eixo X, escrito sob o gráfico. O eixo Y é o título do cartão */
  axisLabel?: string;
   /** Mostra sempre quantas observações cada ponto tem, e não só quando são menos que as seeds */
  showCount?: boolean;
  foot?: string;
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

  const byX = useMemo(() => {
    const table = new Map<string, Map<number, BandPoint>>();
    lines.forEach((line) =>
      table.set(lineKey(line), new Map(line.points.map((p) => [p.x, p])))
    );
    return table;
  }, [lines]);

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
          row[bandKey(key)] = point ? spanOf(point) : null;
        });
        return row;
      }),
    [xs, visible, byX]
  );

  const spread = visible.flatMap((line) =>
    line.points.flatMap((point) => spanOf(point) ?? [point.median])
  );
  const scale = paddedScale(spread, { bounds, zeroLine, padding: PADDING });
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
                showCount={showCount}
                dark={dark}
                xLabel={xLabel}
                foot={foot}
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

      {axisLabel && <p className="chart-axis">{axisLabel}</p>}
    </figure>
  );
}

/** No mouse: um período, e o que cada linha mediu nele, em ordem decrescente de mediana */
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
  showCount,
  dark,
  xLabel,
  foot,
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
  showCount: boolean;
  dark: boolean;
  xLabel: (x: number) => string;
  foot: string;
}) {
  if (!active || label === undefined) return null;
  const ink = inkFor(dark);
  const rows = lines
    .map((line) => ({ line, point: byX.get(lineKey(line))?.get(label) }))
    .filter((row): row is { line: SeriesLine; point: BandPoint } => !!row.point)
    .sort((a, b) => b.point.median - a.point.median)
    .map((row) => ({ ...row, span: spanOf(row.point) }));
  if (!rows.length) return null;

  return (
    <div className="tooltip">
      <div className="tooltip-title">{xLabel(label)}</div>
      {rows.map(({ line, point, span }) => (
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
              {span ? ` ${format(span[0])}–${format(span[1])}` : ""}
              {showCount || point.n < runs ? ` · n=${point.n}` : ""}
            </span>
          </span>
        </div>
      ))}
      <div className="tooltip-foot">{foot}</div>
    </div>
  );
}
