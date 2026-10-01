import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/** Paleta categórica de 8 posições, validada para daltonismo e contraste nas
 * duas superfícies (clara #ffffff, escura #212227). A cor segue o curso, nunca
 * a posição na lista: filtrar cursos não repinta os que sobram. */
const PALETTE_LIGHT = [
  "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
  "#e87ba4", "#008300", "#4a3aa7", "#e34948",
];
const PALETTE_DARK = [
  "#3987e5", "#d95926", "#199e70", "#c98500",
  "#d55181", "#008300", "#9085e9", "#e66767",
];

export const MAX_SERIES = PALETTE_LIGHT.length;

const INK = {
  light: { muted: "#898781", secondary: "#52514e", grid: "#e1e0d9", axis: "#c3c2b7", surface: "#ffffff" },
  dark: { muted: "#898781", secondary: "#c3c2b7", grid: "#2c2c2a", axis: "#383835", surface: "#212227" },
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

export function courseColors(courses: string[], dark: boolean): Record<string, string> {
  const palette = dark ? PALETTE_DARK : PALETTE_LIGHT;
  return Object.fromEntries(courses.map((course, i) => [course, palette[i % palette.length]]));
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

/** Cor da linha agregada — o total, que não é curso nem geração, e sim a soma
 * deles. Tinta neutra de propósito: fora da paleta categórica, ninguém lê o
 * total como "mais um curso", e ela não rouba nenhuma cor dos parciais. */
const AGGREGATE = { light: "#52514e", dark: "#c3c2b7" };

export function totalColor(label: string, dark: boolean): Record<string, string> {
  return { [label]: AGGREGATE[dark ? "dark" : "light"] };
}

export type SeriesPoint = { x: string } & Record<string, number | string>;

export const formatRatio = (value: number) => value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const formatCount = (value: number) => value.toLocaleString("pt-BR", { maximumFractionDigits: 1 });

function Tip({
  active,
  payload,
  label,
  colors,
  format,
  dark,
}: {
  active?: boolean;
  payload?: { dataKey?: string | number; value?: number }[];
  label?: string;
  colors: Record<string, string>;
  format: (value: number) => string;
  dark: boolean;
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
          <span className="swatch" style={{ background: colors[String(row.dataKey)] }} />
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
  hint,
  data,
  courses,
  colors,
  domain,
  format = formatRatio,
  zeroLine = false,
  band = false,
}: {
  title: string;
  hint?: string;
  data: SeriesPoint[];
  courses: string[];
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
  const labelEnds = !band && courses.length > 1 && courses.length <= 4 && data.length > 1;

  return (
    <figure className="chart-card">
      <figcaption>
        <h3>{title}</h3>
        {hint && <p>{hint}</p>}
      </figcaption>

      <div className="legend">
        {courses.map((course) => (
          <span className="legend-item" key={course}>
            <span className="swatch" style={{ background: colors[course] }} />
            {course}
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
          {courses.map((course) => (
            <Line
              key={course}
              type="monotone"
              dataKey={course}
              stroke={colors[course]}
              strokeWidth={2}
              isAnimationActive={false}
              connectNulls
              dot={showDots ? { r: 3, strokeWidth: 0, fill: colors[course] } : false}
              activeDot={{ r: 4, stroke: ink.surface, strokeWidth: 2 }}
              label={
                labelEnds
                  ? (props: { x?: string | number; y?: string | number; index?: number }) => {
                      if (props.index !== data.length - 1) return <g key="skip" />;
                      return (
                        <text
                          key={course}
                          x={Number(props.x ?? 0) + 6}
                          y={Number(props.y ?? 0) + 4}
                          fill={ink.secondary}
                          fontSize={11}
                        >
                          {course.length > 12 ? `${course.slice(0, 11)}…` : course}
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
