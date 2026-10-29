import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/** Paleta categórica de 8 posições, validada para daltonismo e contraste nas
 * duas superfícies (clara #ffffff, escura #262624 — o `--panel` de
 * `styles.css`, que é o fundo de todo card de gráfico). A cor segue a série,
 * nunca a posição na lista: filtrar séries não repinta as que sobram. */
const PALETTE_LIGHT = [
  "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
  "#e87ba4", "#008300", "#4a3aa7", "#e34948",
];
const PALETTE_DARK = [
  "#3987e5", "#d95926", "#199e70", "#c98500",
  "#d55181", "#008300", "#9085e9", "#e66767",
];

const INK = {
  light: { muted: "#898781", secondary: "#52514e", grid: "#e1e0d9", axis: "#c3c2b7", surface: "#ffffff" },
  dark: { muted: "#898781", secondary: "#c3c2b7", grid: "#2f2f2c", axis: "#3b3a36", surface: "#262624" },
};

export function usePrefersDark(): boolean {
  const [dark, setDark] = useState(
    () => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false
  );
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const update = (event: MediaQueryListEvent) => setDark(event.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return dark;
}

export function categoricalColors(labels: string[], dark: boolean): Record<string, string> {
  const palette = dark ? PALETTE_DARK : PALETTE_LIGHT;
  return Object.fromEntries(labels.map((label, i) => [label, palette[i % palette.length]]));
}

/** Rampa para séries *ordenadas* — as gerações de alunos, em que a posição na
 * lista quer dizer alguma coisa. A matiz dá quase uma volta pelo círculo
 * cromático conforme o número cresce, e a luminosidade sobe junto: matiz
 * sozinha colapsa em protanopia e deuteranopia (azul e roxo viram a mesma
 * coisa), e é a luminosidade que sobrevive aos dois. Os extremos de cada
 * superfície foram escolhidos para a rampa ficar dentro da faixa de
 * luminosidade, acima do piso de croma e com contraste >= 3:1 contra o fundo.
 *
 * Diferente da paleta categórica, aqui vizinhos *devem* ser parecidos — o que
 * se lê não é "qual geração é esta" (isso a legenda e a tabela dizem), e sim o
 * sentido do gradiente: geração antiga de um lado, recente do outro. */
const RAMP = {
  light: { from: 0.44, to: 0.64, chroma: 0.16 },
  dark: { from: 0.56, to: 0.7, chroma: 0.15 },
};
const RAMP_FROM_HUE = 250; // azul
const RAMP_HUE_SWEEP = 300; // graus até a última série; menos que 360 para as pontas não se encontrarem

function oklchToLinearRgb(lightness: number, chroma: number, hue: number): number[] {
  const radians = (hue * Math.PI) / 180;
  const a = chroma * Math.cos(radians);
  const b = chroma * Math.sin(radians);
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
}

const channel = (value: number) => {
  const gamma = value <= 0.0031308 ? 12.92 * value : 1.055 * value ** (1 / 2.4) - 0.055;
  return Math.round(Math.min(1, Math.max(0, gamma)) * 255)
    .toString(16)
    .padStart(2, "0");
};

function oklchToHex(lightness: number, chroma: number, hue: number): string {
  // Fora do gamute do sRGB os canais estouram e truncar viraria outra cor:
  // baixa-se o croma até caber, que é o que preserva matiz e luminosidade.
  let c = chroma;
  let rgb = oklchToLinearRgb(lightness, c, hue);
  while (c > 0 && rgb.some((value) => value < -1e-4 || value > 1 + 1e-4)) {
    c -= 0.002;
    rgb = oklchToLinearRgb(lightness, c, hue);
  }
  return `#${rgb.map(channel).join("")}`;
}

/** A rampa é calculada sobre a lista **inteira** de séries, nunca sobre a
 * filtrada: esconder uma geração não pode repintar as que ficaram. */
export function rampColors(labels: string[], dark: boolean): Record<string, string> {
  const { from, to, chroma } = dark ? RAMP.dark : RAMP.light;
  const steps = Math.max(1, labels.length - 1);
  return Object.fromEntries(
    labels.map((label, i) => {
      const t = i / steps;
      return [
        label,
        oklchToHex(from + (to - from) * t, chroma, (RAMP_FROM_HUE + RAMP_HUE_SWEEP * t) % 360),
      ];
    })
  );
}

/** Rampa de uma **faixa**: séries que são as pontas e o meio de uma mesma
 * grandeza — mínimo/média/máximo, demanda potencial/efetiva —, e não categorias
 * diferentes. Matiz única e luminosidade monotônica, do mais forte (a série de
 * cima) ao mais claro: a cor diz a ordem, e não há identidade a distinguir.
 *
 * Diferente da rampa das gerações, aqui a matiz **não** anda: espalhá-la faria
 * duas leituras do mesmo número parecerem grandezas sem relação, que é
 * exatamente o contrário do que a faixa quer mostrar.
 *
 * Os extremos passam a validação ordinal nas duas superfícies — L monotônica,
 * ΔL ≥ 0,06 entre vizinhos e ponta clara acima de 2:1 contra o fundo (2,66:1 na
 * clara, 3,72:1 na escura). */
const BAND = {
  light: { from: 0.42, to: 0.7, chroma: 0.12 },
  dark: { from: 0.84, to: 0.58, chroma: 0.11 },
};
const BAND_HUE = 250; // o mesmo azul da primeira posição da paleta

export function bandColors(labels: string[], dark: boolean): Record<string, string> {
  const { from, to, chroma } = dark ? BAND.dark : BAND.light;
  const steps = Math.max(1, labels.length - 1);
  return Object.fromEntries(
    labels.map((label, i) => [
      label,
      oklchToHex(from + (to - from) * (i / steps), chroma, BAND_HUE),
    ])
  );
}

/** Paleta de **estado**, fixa nos dois temas e deliberadamente fora da
 * categórica: ela diz se algo passa ou não passa, nunca "qual série é esta".
 * Como a amarela fica abaixo de 3:1 na superfície clara, toda leitura que a
 * use precisa vir com rótulo em palavras ao lado — é a mitigação prevista, e
 * por isso o histograma colorido por estado exige legenda. */
export const STATUS = { good: "#0ca30c", warning: "#fab219", critical: "#d03b3b" };

/** Cor da linha agregada — o total, que não é uma geração, e sim a soma
 * delas. Tinta neutra de propósito: fora da paleta categórica, ninguém lê o
 * total como "mais um recorte", e ela não rouba nenhuma cor dos parciais. */
const AGGREGATE = { light: "#52514e", dark: "#c3c2b7" };

export function totalColor(label: string, dark: boolean): Record<string, string> {
  return { [label]: AGGREGATE[dark ? "dark" : "light"] };
}

export type SeriesPoint = { x: string | number } & Record<string, number | string>;

export const formatRatio = (value: number) => value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const formatCount = (value: number) => value.toLocaleString("pt-BR", { maximumFractionDigits: 1 });

function Tip({
  active,
  payload,
  label,
  colors,
  format,
  dark,
  fillFor,
}: {
  active?: boolean;
  payload?: { dataKey?: string | number; value?: number }[];
  label?: string;
  colors: Record<string, string>;
  format: (value: number) => string;
  dark: boolean;
  /** Cor do marcador quando ela é da **faixa**, e não da série — o histograma
   * pintado por estado tem uma cor por barra, e o `dataKey` é o mesmo em
   * todas. */
  fillFor?: (label: string | undefined) => string | undefined;
}) {
  if (!active || !payload?.length) return null;
  const rows = payload
    .filter((row) => typeof row.value === "number")
    .sort((a, b) => (b.value as number) - (a.value as number));
  return (
    <div className="tooltip">
      <div className="tooltip-title">{label}</div>
      {rows.map((row) => (
        <div className="tooltip-row" key={String(row.dataKey)}>
          <span
            className="swatch"
            style={{ background: fillFor?.(label) ?? colors[String(row.dataKey)] }}
          />
          <span className="tooltip-label">{String(row.dataKey)}</span>
          <span className="tooltip-value" style={{ color: INK[dark ? "dark" : "light"].secondary }}>
            {format(row.value as number)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function MetricChart({
  title,
  data,
  series,
  colors,
  domain,
  format = formatRatio,
  zeroLine = false,
  band = false,
}: {
  title: string;
  data: SeriesPoint[];
  /** Os `dataKey` de cada linha, na ordem em que entram na legenda. */
  series: string[];
  colors: Record<string, string>;
  domain?: [number | "auto", number | "auto"];
  format?: (value: number) => string;
  zeroLine?: boolean;
  /** Séries que são leituras ordenadas da mesma grandeza (`bandColors`), e não
   * entidades diferentes. */
  band?: boolean;
}) {
  const dark = usePrefersDark();
  const ink = INK[dark ? "dark" : "light"];
  // Poucos pontos: a linha some se não houver marcadores (com um período só,
  // o gráfico inteiro é um ponto).
  const showDots = data.length <= 12;
  // Rótulo direto na ponta da linha: só até 4 séries, senão os rótulos colidem.
  // Com uma série só não há o que distinguir, e a legenda já diz de quem é a
  // linha: repetir o nome na ponta seria ruído. Numa faixa a identidade é a
  // própria ordem vertical — e, quando as linhas se encontram (um preço que
  // despenca ao piso), os rótulos cairiam empilhados no mesmo ponto.
  const labelEnds = !band && series.length > 1 && series.length <= 4 && data.length > 1;

  return (
    <figure className="chart-card">
      <figcaption>
        <h3>{title}</h3>
      </figcaption>

      <div className="legend">
        {series.map((name) => (
          <span className="legend-item" key={name}>
            <span className="swatch" style={{ background: colors[name] }} />
            {name}
          </span>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 8, right: labelEnds ? 78 : 12, bottom: 4, left: 0 }}>
          <CartesianGrid stroke={ink.grid} vertical={false} />
          <XAxis
            dataKey="x"
            tick={{ fill: ink.muted, fontSize: 11 }}
            tickLine={false}
            stroke={ink.axis}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={domain}
            tick={{ fill: ink.muted, fontSize: 11 }}
            tickLine={false}
            stroke={ink.axis}
            width={46}
            tickFormatter={format}
          />
          {zeroLine && <ReferenceLine y={0} stroke={ink.axis} />}
          <Tooltip
            cursor={{ stroke: ink.axis }}
            content={<Tip colors={colors} format={format} dark={dark} />}
          />
          {series.map((name) => (
            <Line
              key={name}
              type="monotone"
              dataKey={name}
              stroke={colors[name]}
              strokeWidth={2}
              isAnimationActive={false}
              connectNulls
              dot={showDots ? { r: 3, strokeWidth: 0, fill: colors[name] } : false}
              activeDot={{ r: 4, stroke: ink.surface, strokeWidth: 2 }}
              label={
                labelEnds
                  ? (props: { x?: string | number; y?: string | number; index?: number }) => {
                      if (props.index !== data.length - 1) return <g key="skip" />;
                      return (
                        <text
                          key={name}
                          x={Number(props.x ?? 0) + 6}
                          y={Number(props.y ?? 0) + 4}
                          fill={ink.secondary}
                          fontSize={11}
                        >
                          {name.length > 12 ? `${name.slice(0, 11)}…` : name}
                        </text>
                      );
                    }
                  : undefined
              }
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </figure>
  );
}

/** ---------------------------------------------------------------------------
 * Boxplot — a forma da comparação entre mecanismos
 *
 * Aqui o eixo horizontal não é o tempo: cada caixa é a **distribuição** de uma
 * métrica sobre as N execuções de um mecanismo, e o que se lê é a mediana e a
 * dispersão. Uma média sozinha não serviria: se as duas caixas se sobrepõem, a
 * diferença entre as médias pode ser do sorteio; se não se sobrepõem, não é.
 *
 * Não há primitiva de boxplot no recharts, então o desenho é SVG direto. São
 * poucas marcas e a geometria é toda explícita, o que acaba sendo mais simples
 * do que encaixá-la numa biblioteca de séries temporais.
 * ------------------------------------------------------------------------- */

/** O resumo de cinco números de uma amostra, mais os pontos fora dos bigodes. */
export interface BoxStats {
  n: number;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  /** Pontas dos bigodes: o valor mais extremo ainda dentro de 1,5 IQR do
   * quartil — a convenção de Tukey. O que sobra vira ponto solto. */
  low: number;
  high: number;
  outliers: number[];
}

/** Quantil por interpolação linear entre as ordens estatísticas (o método 7,
 * padrão do R e do numpy). Com N pequeno a escolha do método desloca os
 * quartis visivelmente, então convém que seja a mesma que qualquer conferência
 * externa usaria. */
function quantile(sorted: number[], p: number): number {
  if (sorted.length === 1) return sorted[0];
  const position = p * (sorted.length - 1);
  const floor = Math.floor(position);
  const rest = position - floor;
  return rest === 0
    ? sorted[floor]
    : sorted[floor] + rest * (sorted[floor + 1] - sorted[floor]);
}

export function boxStats(values: number[]): BoxStats | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const q1 = quantile(sorted, 0.25);
  const median = quantile(sorted, 0.5);
  const q3 = quantile(sorted, 0.75);
  const fence = 1.5 * (q3 - q1);
  const inside = sorted.filter((v) => v >= q1 - fence && v <= q3 + fence);
  return {
    n: sorted.length,
    min: sorted[0],
    q1,
    median,
    q3,
    max: sorted[sorted.length - 1],
    low: inside.length ? inside[0] : sorted[0],
    high: inside.length ? inside[inside.length - 1] : sorted[sorted.length - 1],
    outliers: sorted.filter((v) => v < q1 - fence || v > q3 + fence),
  };
}

/** Domínio e marcas arredondados a passos legíveis (1, 2, 2,5 ou 5 vezes uma
 * potência de 10), estendidos até cobrir os dados. */
export function niceScale(low: number, high: number, count = 4) {
  if (!(high > low)) {
    const pad = Math.abs(high) * 0.05 || 0.05;
    low = high - pad;
    high = high + pad;
  }
  const rough = (high - low) / count;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const normalized = rough / magnitude;
  const step =
    (normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10) *
    magnitude;
  const from = Math.floor(low / step) * step;
  const to = Math.ceil(high / step) * step;
  const ticks: number[] = [];
  for (let i = 0; from + i * step <= to + step / 2; i++) ticks.push(from + i * step);
  return { from, to: ticks[ticks.length - 1], ticks };
}

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
    observer.current = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width)
    );
    observer.current.observe(node);
  }, []);
  useEffect(() => () => observer.current?.disconnect(), []);
  return [ref, width];
}

export const PLOT = { top: 12, right: 16, bottom: 30, left: 50, height: 232 };
/** Caixa fina, como toda marca: a leitura é a posição e a altura, nunca a
 * largura, que não codifica nada. */
export const BOX_WIDTH = 30;

export function BoxPlot({
  title,
  groups,
  colors,
  format = formatRatio,
  bounds,
  zeroLine = false,
}: {
  title: string;
  /** Uma caixa por grupo, na ordem em que entram no eixo e na legenda.
   * `short` é o rótulo do eixo: a legenda carrega o nome inteiro, e embaixo da
   * caixa cabe pouco — um nome longo colide com o do vizinho. */
  groups: { label: string; short?: string; values: number[] }[];
  colors: Record<string, string>;
  format?: (value: number) => string;
  /** Limites naturais da métrica (ψ̄ não passa de 1; λ vive em [-1, 1]). O
   * domínio é folgado em torno dos dados, mas nunca além deles — uma caixa
   * encostada no teto tem de se ler como encostada no teto. */
  bounds?: [number, number];
  /** Marca o zero quando o sinal da métrica é o que se lê (λ). */
  zeroLine?: boolean;
}) {
  const dark = usePrefersDark();
  const ink = INK[dark ? "dark" : "light"];
  const [ref, width] = useWidth();
  const [hovered, setHovered] = useState<number | null>(null);

  const boxes = groups.map((group) => ({ ...group, stats: boxStats(group.values) }));
  const all = groups.flatMap((group) => group.values);

  const scale = (() => {
    if (!all.length) return { from: 0, to: 1, ticks: [0, 1] };
    let low = Math.min(...all);
    let high = Math.max(...all);
    if (zeroLine) {
      low = Math.min(low, 0);
      high = Math.max(high, 0);
    }
    // Folga proporcional à dispersão: as caixas ficam quase coladas quando as
    // execuções concordam, e é justamente isso que se quer ver.
    const pad = (high - low) * 0.25 || Math.max(Math.abs(high) * 0.05, 0.01);
    const nice = niceScale(low - pad, high + pad);
    return bounds
      ? { ...nice, from: Math.max(nice.from, bounds[0]), to: Math.min(nice.to, bounds[1]) }
      : nice;
  })();

  const plotWidth = Math.max(0, width - PLOT.left - PLOT.right);
  const plotHeight = PLOT.height - PLOT.top - PLOT.bottom;
  const y = (value: number) =>
    PLOT.top +
    plotHeight * (1 - (value - scale.from) / (scale.to - scale.from || 1));
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
                      {/* A caixa é o intervalo interquartil: metade central da
                          amostra. Preenchimento lavado, contorno fino. */}
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
                          compara entre as duas caixas. */}
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
                          {/* Rótulo direto: só a mediana, ao lado da caixa — e
                          nunca um número por ponto. Em tinta de texto: a
                          identidade vem da caixa colorida ao lado.

                          Ele só aparece se couber **antes da caixa vizinha**.
                          Espremer, virar de lado ou deixar transbordar põe o
                          número de uma caixa em cima da outra, que é pior do
                          que não ter rótulo: a mediana continua no tooltip e
                          nas tabelas, e a comparação de posições — que é o que
                          o gráfico existe para mostrar — não depende dele. */}
                      {(() => {
                        const text = format(box.stats.median);
                        // Largura aproximada do texto a 11px; basta para
                        // decidir, e medir de verdade exigiria render.
                        const end = x + half + 7 + text.length * 6.4;
                        const nextBox =
                          index + 1 < boxes.length
                            ? center(index + 1) - half
                            : width - PLOT.right + 12;
                        if (end > nextBox) return null;
                        return (
                          <text
                            x={x + half + 7}
                            y={y(box.stats.median) + 4}
                            fontSize={11}
                            fill={ink.secondary}
                          >
                            {text}
                          </text>
                        );
                      })()}
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
              right: center(hovered) > width / 2 ? width - center(hovered) + 20 : undefined,
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


/** Geometria do histograma. O eixo de divisas é desenhado em HTML, e não pelo
 * Recharts, porque o eixo categórico dele põe rótulo no **centro** da barra e o
 * que se quer aqui é o valor **entre** barras. Para alinhar, os rótulos recebem
 * a mesma caixa de plotagem do gráfico: ela começa depois do eixo y e termina
 * antes da margem direita. */
const HISTOGRAM = { height: 150, left: 40, right: 12 };

/** Histograma de uma distribuição: **uma** série, então sem legenda — o título
 * diz de quem é a barra — e matiz única, porque as barras são faixas da mesma
 * grandeza e não categorias diferentes.
 *
 * O eixo x traz as **divisas** das faixas, de 0 a 1, e não a contagem de 1 a n:
 * a grandeza é contínua e o que importa é onde a faixa começa e termina. O eixo
 * y vai de 0 a 1 fixo, porque estes gráficos existem para serem comparados
 * entre si e um eixo que se ajusta a cada um faria distribuições diferentes
 * parecerem iguais. */
/** ---------------------------------------------------------------------------
 * Curva de densidade — a forma que um parâmetro produz
 *
 * Diferente do histograma, aqui não há dado contado: a tela de configuração
 * desenha a distribuição que os parâmetros **implicam**, antes de qualquer
 * execução. Barras sugeririam contagem onde não há nenhuma; a área sob a curva
 * é o que diz "a massa está aqui".
 *
 * O eixo vertical fica **escondido** de propósito: a altura de uma densidade é
 * por unidade do eixo x, e esse número não se lê. O que se lê é a forma, e, no
 * mouse, a massa acumulada até o ponto.
 * ------------------------------------------------------------------------- */

/** Corte que parte a curva em duas cores — a nota mínima. Antes dele a área é
 * de quem reprova, depois é de quem aprova, e o encontro das duas *é* o corte:
 * não há faixa dividida, porque não há faixa. */
export interface DensitySplit {
  at: number;
  below: string;
  above: string;
  labels: [string, string];
}

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
  points: { x: number; y: number; cum: number }[];
  domain: [number, number];
  split?: DensitySplit;
  controls?: ReactNode;
  /** Os números que a curva não mostra sozinha — o valor mais provável e, nas
   * notas, a aprovação. Vão ao pé do card, e não no título, porque são leitura
   * do desenho e não identificação dele. */
  footer?: ReactNode;
  /** Identificador do gradiente no SVG — dois gráficos na mesma página não
   * podem dividir o mesmo `id`. */
  id: string;
}) {
  const dark = usePrefersDark();
  const ink = INK[dark ? "dark" : "light"];
  const single = (dark ? PALETTE_DARK : PALETTE_LIGHT)[0];
  const [low, high] = domain;
  const span = high - low || 1;
  // Onde o corte cai, em fração da largura do gráfico. As duas paradas do
  // gradiente ficam no mesmo ponto, de modo que a cor vira de uma vez — é uma
  // divisa, não um degradê.
  const cut = Math.min(1, Math.max(0, (split ? split.at - low : 0) / span));
  const digits = Math.max(0, Math.ceil(-Math.log10(span / 10)));
  const tick = (value: number) =>
    value.toLocaleString("pt-BR", { maximumFractionDigits: digits });
  // O mouse cai **entre** as marcas do eixo, então ele precisa de uma casa a
  // mais: no eixo das notas as marcas são inteiras, e a nota não é — ela sai do
  // motor arredondada a um décimo, e é assim que tem de aparecer.
  // Topo da régua: o primeiro inteiro acima do pico. O piso é 1, de modo que
  // uma curva baixa — a das notas, cujo pico é 0,21 — se leia como baixa, em
  // vez de a régua se fechar em torno dela.
  const tallest = points.reduce((max, point) => Math.max(max, point.y), 0);
  const ceiling = Math.floor(tallest) + 1;
  const heightTicks = [0, 0.25, 0.5, 0.75, 1].map((part) => part * ceiling);
  const heightDigits = ceiling >= 10 ? 0 : 2;
  // No tooltip a altura vai com uma casa a mais que o eixo: ali o ponto é um
  // só, e arredondá-lo à casa da régua apagaria a diferença entre dois pontos
  // vizinhos da curva.
  const height = (value: number) =>
    value.toLocaleString("pt-BR", {
      minimumFractionDigits: heightDigits + 1,
      maximumFractionDigits: heightDigits + 1,
    });
  const exact = (value: number) =>
    value.toLocaleString("pt-BR", {
      minimumFractionDigits: digits + 1,
      maximumFractionDigits: digits + 1,
    });

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

      <ResponsiveContainer width="100%" height={150}>
        <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="1" y2="0">
              <stop offset={cut} stopColor={split ? split.below : single} />
              <stop offset={cut} stopColor={split ? split.above : single} />
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
          {/* A régua vai de 0 ao primeiro inteiro acima do pico, de modo que
              a curva cabe inteira e o topo é um número redondo. O que ela mede
              é **densidade**: massa por unidade do eixo x, com área 1 sob a
              curva. Daí ela passar de 1 quando o eixo x é estreito — na fração
              de utilidade, cuja régua mede 0,04, o pico beira 100 e a área
              ainda vale 1. */}
          <YAxis
            domain={[0, ceiling]}
            ticks={heightTicks}
            tick={{ fill: ink.muted, fontSize: 10 }}
            tickLine={false}
            stroke={ink.axis}
            width={40}
            tickFormatter={(value: number) =>
              value.toLocaleString("pt-BR", {
                minimumFractionDigits: heightDigits,
                maximumFractionDigits: heightDigits,
              })
            }
          />
          <Tooltip
            cursor={{ stroke: ink.axis }}
            content={<CumulativeTip format={exact} height={height} split={split} dark={dark} />}
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

/** No mouse: o ponto da curva (x e y) e o **percentil** dele — a massa
 * acumulada até ali, que é a única leitura de probabilidade que uma densidade
 * dá num ponto só. */
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
  const ink = INK[dark ? "dark" : "light"].secondary;
  // De que lado do corte o ponto está — a mesma comparação que o motor faz com
  // a nota mínima, inclusive no empate: a nota igual a n_min aprova.
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
  /** Uma cor por faixa, quando a cor diz um **estado** da faixa e não a
   * identidade da série. Ausente, todas saem na matiz única. */
  binColors?: string[];
  /** Obrigatória junto de `binColors`: cor de estado nunca carrega significado
   * sozinha. */
  legend?: { color: string; label: string }[];
  /** Campos que configuram **este gráfico**, e não a simulação. Ficam dentro
   * do card, logo abaixo do título, que é o que deixa claro de quem eles são. */
  controls?: ReactNode;
}) {
  const dark = usePrefersDark();
  const ink = INK[dark ? "dark" : "light"];
  // Matiz única da paleta: a primeira posição, a mesma de uma série solitária
  // em qualquer outro gráfico.
  const fill = (dark ? PALETTE_DARK : PALETTE_LIGHT)[0];
  // n faixas têm n + 1 divisas, igualmente espaçadas no domínio.
  const [low, high] = domain;
  const edges = Array.from(
    { length: fractions.length + 1 },
    (_, i) => low + ((high - low) * i) / fractions.length
  );
  // Casas decimais pela **régua**, e não por faixas de grandeza: o número de
  // casas é o menor que ainda escreve todas as divisas **distintas**. Em [0, 10]
  // isso dá zero; em [0, 1], uma; num eixo que vai até 0,043 — a fração de
  // utilidade de uma grade de 60 disciplinas — dá três, que é o que impede a
  // régua de sair "0 0 0 0". Arredondar o rótulo é normal numa régua; repetir
  // dois rótulos diferentes não é.
  const MAX_DIGITS = 6;
  const distinct = (digits: number) => {
    const seen = new Set(edges.map((edge) => edge.toFixed(digits)));
    return seen.size === edges.length;
  };
  let edgeDigits = 0;
  while (edgeDigits < MAX_DIGITS && !distinct(edgeDigits)) edgeDigits += 1;
  // As pontas saem sem casas decimais — é o 0 e o 1 do domínio, e "0,10" no
  // lugar de "1" se lê como outro número.
  const edgeLabel = (index: number) =>
    index === 0 || index === fractions.length
      ? edges[index].toLocaleString("pt-BR", { maximumFractionDigits: edgeDigits })
      : edges[index].toLocaleString("pt-BR", {
          minimumFractionDigits: edgeDigits,
          maximumFractionDigits: edgeDigits,
        });
  // Separador do par: vírgula onde ela está livre, ponto e vírgula onde a
  // vírgula já é a decimal — "[0,1, 0,2)" se lê como quatro números.
  const pairSeparator = edgeDigits > 0 ? "; " : ", ";
  // A faixa se identifica pelo intervalo que cobre, não pela posição na lista:
  // "[7, 8)" é o que se lê na régua de divisas, e "3" não quer dizer nada. O
  // intervalo é fechado à esquerda e aberto à direita, **menos o último**, que
  // é fechado dos dois lados: é nele que o máximo do domínio cai, por convenção
  // de `grade_distribution` e `utility_distribution`. Daí a nota 10 contar como
  // aprovação e não cair fora do gráfico.
  const data = fractions.map((value, index) => ({
    x: `[${edgeLabel(index)}${pairSeparator}${edgeLabel(index + 1)}${
      index === fractions.length - 1 ? "]" : ")"
    }`,
    "fração": value,
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

      <ResponsiveContainer width="100%" height={HISTOGRAM.height}>
        <BarChart
          data={data}
          margin={{ top: 8, right: HISTOGRAM.right, bottom: 0, left: 0 }}
        >
          <CartesianGrid stroke={ink.grid} vertical={false} />
          {/* Sem rótulo: quem rotula é a régua de divisas abaixo. */}
          <XAxis dataKey="x" tick={false} tickLine={false} height={6} stroke={ink.axis} />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: ink.muted, fontSize: 10 }}
            tickLine={false}
            stroke={ink.axis}
            width={HISTOGRAM.left}
            tickFormatter={format}
          />
          <Tooltip
            cursor={{ fill: ink.grid }}
            content={
              <Tip colors={{ "fração": fill }} format={format} dark={dark} fillFor={colorOf} />
            }
          />
          <Bar dataKey="fração" fill={fill} isAnimationActive={false} radius={[4, 4, 0, 0]}>
            {binColors &&
              data.map((row, index) => <Cell key={row.x} fill={binColors[index] ?? fill} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div
        className="histogram-edges"
        style={{ marginLeft: HISTOGRAM.left, marginRight: HISTOGRAM.right }}
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
