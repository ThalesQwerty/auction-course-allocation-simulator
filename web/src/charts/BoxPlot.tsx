/** O eixo X colapsado: uma caixa por modelo, sobre as **seeds** */
import { inkFor, usePrefersDark } from "./theme";

/** Uma caixa já reduzida. A API a devolve pronta: a tela desenha, não calcula */
export interface Box {
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  n: number;
}

export interface BoxRow {
  key: string;
  label: string;
  color: string;
  box: Box | null;
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
  const stats = rows.map((row) => ({ row, box: row.box }));
  const present = stats.filter((entry) => entry.box !== null);

  const values = present.flatMap((entry) =>
    entry.box ? [entry.box.min, entry.box.max] : []
  );
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
          const { min, max } = stat;
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
