/** O eixo X colapsado: uma caixa por modelo, sobre as **seeds**.
 *
 * As linhas da tela mostram a mediana entre as simulações em cada ponto do
 * tempo; aqui o tempo some e o que sobra é a distribuição do número da tabela.
 * A pergunta é outra, e é a que o texto precisa: **o vão entre os mecanismos é
 * maior que o ruído entre populações?** Caixas que não se sobrepõem respondem
 * que sim.
 *
 * A caixa é sobre as seeds, nunca sobre os alunos. A dispersão entre alunos é
 * o que as linhas de quantil mostram, e as duas respondem a perguntas
 * diferentes — misturá-las numa caixa só seria erro de leitura.
 *
 * Desenho convencional: caixa do 1º ao 3º quartil, traço na mediana, bigodes
 * até os extremos. Sem outliers destacados — com 20 seeds a amostra é pequena
 * demais para a regra de 1,5·IQR dizer alguma coisa.
 */
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

  // A régua cobre o contradomínio pedido, mas nunca menos que a amostra: uma
  // grandeza em [0, 1] com todas as caixas entre 0,2 e 0,3 se leria como três
  // riscos colados no eixo.
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
