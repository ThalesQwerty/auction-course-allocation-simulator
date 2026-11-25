/** O eixo X colapsado: uma caixa por modelo, sobre as **seeds** */
import { boxStats } from "../equations";
import { inkFor, usePrefersDark } from "./theme";

export interface BoxRow {
  key: string;
  label: string;
  color: string;
  values: number[];
}

const HEIGHT = 34;
const PAD = 10;

export function BoxPlot({
  title,
  rows,
  bounds,
  format,
}: {
  title: string;
  rows: BoxRow[];
  bounds: [number, number];
  format: (value: number) => string;
}) {
  const dark = usePrefersDark();
  const ink = inkFor(dark);
  const stats = rows.map((row) => ({ row, box: boxStats(row.values) }));
  const present = stats.filter((entry) => entry.box !== null);

  const values = present.flatMap((entry) => entry.row.values);
  const low = Math.min(bounds[0], ...values);
  const high = Math.max(bounds[1], ...values);
  const span = high - low || 1;
  const at = (value: number) => PAD + ((value - low) / span) * (100 - 2 * PAD);

  if (!present.length) return null;

  return (
    <figure className="boxplot">
      <figcaption>{title}</figcaption>
      <svg
        viewBox={`0 0 100 ${present.length * HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={title}
      >
        {present.map(({ row, box }, index) => {
          const stat = box!;
          const y = index * HEIGHT + HEIGHT / 2;
          const min = Math.min(...row.values);
          const max = Math.max(...row.values);
          return (
            <g key={row.key}>
              <line
                x1={at(min)}
                x2={at(max)}
                y1={y}
                y2={y}
                stroke={row.color}
                strokeWidth={0.6}
              />
              <rect
                x={at(stat.q1)}
                y={y - 7}
                width={Math.max(at(stat.q3) - at(stat.q1), 0.6)}
                height={14}
                fill={row.color}
                fillOpacity={0.22}
                stroke={row.color}
                strokeWidth={0.6}
              />
              <line
                x1={at(stat.median)}
                x2={at(stat.median)}
                y1={y - 7}
                y2={y + 7}
                stroke={row.color}
                strokeWidth={1.4}
              />
            </g>
          );
        })}
      </svg>
      <dl className="boxplot-legend">
        {present.map(({ row, box }) => (
          <div key={row.key}>
            <dt>
              <span className="swatch" style={{ background: row.color }} />
              {row.label}
            </dt>
            <dd style={{ color: ink.secondary }}>{format(box!.median)}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}
