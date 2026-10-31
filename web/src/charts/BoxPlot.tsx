/** O boxplot — a forma da comparação entre modelos.
 *
 * Aqui o eixo horizontal não é o tempo: cada caixa é a **distribuição** de
 * uma métrica sobre as N execuções de um modelo, e o que se lê é a mediana e
 * a dispersão. Uma média sozinha não serviria — se as caixas se sobrepõem, a
 * diferença entre as medianas pode ser do sorteio; se não se sobrepõem, não
 * é.
 *
 * Não há primitiva de boxplot no recharts, então o desenho é SVG direto. São
 * poucas marcas e a geometria é toda explícita, o que acaba sendo mais
 * simples do que encaixá-la numa biblioteca de séries temporais.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { boxStats, paddedScale } from "../equations";
import { formatRatio } from "./format";
import { inkFor, usePrefersDark } from "./theme";

const PLOT = { top: 12, right: 16, bottom: 30, left: 50, height: 232 };

/** Caixa fina, como toda marca: a leitura é a posição e a altura, nunca a
 * largura, que não codifica nada. */
const BOX_WIDTH = 30;

/** Folga proporcional à dispersão, para as métricas **sem** contradomínio —
 * o tempo de formatura e a saturação. As que têm (ψ̄, λ, as frações) se
 * desenham na régua inteira delas, e aí não há folga a dar: ver `paddedScale`.
 * Generosa de propósito, porque os bigodes já alcançam os extremos. */
const PADDING = 0.25;

/** Largura aproximada de um caractere a 11px. Basta para decidir se o rótulo
 * cabe; medir de verdade exigiria render. */
const CHAR_WIDTH = 6.4;

/** Largura real do cartão, para o SVG não depender de um viewBox esticado — o
 * texto de um viewBox escalado sai com corpo diferente em cada coluna da
 * grade. */
function useWidth(): [(node: HTMLDivElement | null) => void, number] {
  const [width, setWidth] = useState(0);
  const observer = useRef<ResizeObserver | null>(null);
  const ref = useCallback((node: HTMLDivElement | null) => {
    observer.current?.disconnect();
    if (!node) return;
    setWidth(node.clientWidth);
    observer.current = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.current.observe(node);
  }, []);
  useEffect(() => () => observer.current?.disconnect(), []);
  return [ref, width];
}

export interface BoxGroup {
  label: string;
  /** Rótulo do eixo: a legenda carrega o nome inteiro, e embaixo da caixa
   * cabe pouco — um nome longo colide com o do vizinho. */
  short?: string;
  values: number[];
}

export function BoxPlot({
  title,
  groups,
  colors,
  format = formatRatio,
  bounds,
  zeroLine = false,
}: {
  title: string;
  groups: BoxGroup[];
  colors: Record<string, string>;
  format?: (value: number) => string;
  /** O contradomínio da métrica (ψ̄ vive em [0, 1]; λ em [−1, 1]). Quando os
   * dois limites são finitos, **a régua é ele**: a caixa se desenha na escala
   * da grandeza, e não na da amostra. Com um limite só — a saturação não passa
   * de zero por baixo, mas não tem teto — a régua se ajusta aos dados e é
   * aparada desse lado. */
  bounds?: [number, number];
  /** Marca o zero quando o sinal da métrica é o que se lê (λ). */
  zeroLine?: boolean;
}) {
  const dark = usePrefersDark();
  const ink = inkFor(dark);
  const [ref, width] = useWidth();
  const [hovered, setHovered] = useState<number | null>(null);

  const boxes = groups.map((group) => ({ ...group, stats: boxStats(group.values) }));
  const all = groups.flatMap((group) => group.values);
  const scale = paddedScale(all, { bounds, zeroLine, padding: PADDING });

  const plotWidth = Math.max(0, width - PLOT.left - PLOT.right);
  const plotHeight = PLOT.height - PLOT.top - PLOT.bottom;
  const y = (value: number) =>
    PLOT.top + plotHeight * (1 - (value - scale.from) / (scale.to - scale.from || 1));
  const band = plotWidth / Math.max(1, boxes.length);
  const center = (index: number) => PLOT.left + band * (index + 0.5);

  return (
    <figure className="chart-card">
      <figcaption>
        <h3>{title}</h3>
      </figcaption>

      <div className="legend">
        {groups.map((group) => (
          <span className="legend-item" key={group.label}>
            <span className="swatch" style={{ background: colors[group.label] }} />
            {group.label}
          </span>
        ))}
      </div>

      <div className="boxplot" ref={ref}>
        {width > 0 && (
          <svg width={width} height={PLOT.height} role="img" aria-label={title}>
            {scale.ticks
              .filter((tick) => tick >= scale.from - 1e-9 && tick <= scale.to + 1e-9)
              .map((tick) => (
                <g key={tick}>
                  <line
                    x1={PLOT.left}
                    x2={width - PLOT.right}
                    y1={y(tick)}
                    y2={y(tick)}
                    stroke={ink.grid}
                  />
                  <text
                    x={PLOT.left - 8}
                    y={y(tick) + 4}
                    textAnchor="end"
                    fontSize={11}
                    fill={ink.muted}
                  >
                    {format(tick)}
                  </text>
                </g>
              ))}
            {zeroLine && 0 >= scale.from && 0 <= scale.to && (
              <line
                x1={PLOT.left}
                x2={width - PLOT.right}
                y1={y(0)}
                y2={y(0)}
                stroke={ink.axis}
              />
            )}

            {boxes.map((box, index) => {
              const color = colors[box.label];
              const x = center(index);
              const half = Math.min(BOX_WIDTH, band * 0.4) / 2;
              // O rótulo da mediana só aparece se couber **antes da caixa
              // vizinha**. Espremer, virar de lado ou deixar transbordar põe
              // o número de uma caixa em cima da outra, que é pior do que não
              // ter rótulo: a mediana continua no tooltip e nas tabelas, e a
              // comparação de posições não depende dele.
              const medianLabel = box.stats && format(box.stats.median);
              const labelEnd =
                medianLabel === undefined || medianLabel === null
                  ? Infinity
                  : x + half + 7 + medianLabel.length * CHAR_WIDTH;
              const nextBox =
                index + 1 < boxes.length
                  ? center(index + 1) - half
                  : width - PLOT.right + 12;

              return (
                <g key={box.label}>
                  {box.stats && (
                    <>
                      {/* Bigodes: a extensão dos dados dentro de 1,5 IQR. */}
                      <line
                        x1={x}
                        x2={x}
                        y1={y(box.stats.high)}
                        y2={y(box.stats.low)}
                        stroke={color}
                        strokeWidth={1.5}
                      />
                      {[box.stats.high, box.stats.low].map((value) => (
                        <line
                          key={value}
                          x1={x - half / 2}
                          x2={x + half / 2}
                          y1={y(value)}
                          y2={y(value)}
                          stroke={color}
                          strokeWidth={1.5}
                        />
                      ))}
                      {/* A caixa é o intervalo interquartil: metade central
                          da amostra. Preenchimento lavado, contorno fino. */}
                      <rect
                        x={x - half}
                        width={half * 2}
                        y={y(box.stats.q3)}
                        height={Math.max(1, y(box.stats.q1) - y(box.stats.q3))}
                        rx={2}
                        fill={color}
                        fillOpacity={0.14}
                        stroke={color}
                        strokeWidth={1.5}
                      />
                      {/* A mediana é a única marca grossa: é o número que se
                          compara entre as caixas. */}
                      <line
                        x1={x - half}
                        x2={x + half}
                        y1={y(box.stats.median)}
                        y2={y(box.stats.median)}
                        stroke={color}
                        strokeWidth={3}
                      />
                      {box.stats.outliers.map((value, i) => (
                        <circle
                          key={`${value}-${i}`}
                          cx={x}
                          cy={y(value)}
                          r={4}
                          fill={color}
                          stroke={ink.surface}
                          strokeWidth={2}
                        />
                      ))}
                      {labelEnd <= nextBox && (
                        <text
                          x={x + half + 7}
                          y={y(box.stats.median) + 4}
                          fontSize={11}
                          fill={ink.secondary}
                        >
                          {medianLabel}
                        </text>
                      )}
                    </>
                  )}
                  <text
                    x={x}
                    y={PLOT.height - 10}
                    textAnchor="middle"
                    fontSize={11}
                    fill={ink.muted}
                  >
                    {box.short ?? box.label}
                  </text>
                  {/* Alvo de hover da faixa inteira, bem maior que a caixa. */}
                  <rect
                    x={PLOT.left + band * index}
                    width={band}
                    y={PLOT.top}
                    height={plotHeight}
                    fill="transparent"
                    onMouseEnter={() => setHovered(index)}
                    onMouseLeave={() => setHovered(null)}
                  />
                </g>
              );
            })}
          </svg>
        )}

        {hovered !== null && boxes[hovered]?.stats && (
          <div
            className="tooltip boxplot-tooltip"
            style={{
              left: center(hovered) > width / 2 ? undefined : center(hovered) + 20,
              right:
                center(hovered) > width / 2 ? width - center(hovered) + 20 : undefined,
            }}
          >
            <div className="tooltip-title">
              {boxes[hovered].label} · {boxes[hovered].stats!.n} execuções
            </div>
            {(
              [
                ["máximo", boxes[hovered].stats!.max],
                ["3º quartil", boxes[hovered].stats!.q3],
                ["mediana", boxes[hovered].stats!.median],
                ["1º quartil", boxes[hovered].stats!.q1],
                ["mínimo", boxes[hovered].stats!.min],
              ] as const
            ).map(([label, value]) => (
              <div className="tooltip-row" key={label}>
                <span className="tooltip-label">{label}</span>
                <span className="tooltip-value" style={{ color: ink.secondary }}>
                  {format(value)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </figure>
  );
}
