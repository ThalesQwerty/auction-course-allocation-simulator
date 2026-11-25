/** As cores das faixas de quantil nos gráficos */
import { STATUS } from "./charts";

export const PALETTE = {
  gray: "#8a8984",
  red: STATUS.critical,
  orange: "#eb6834",
  yellow: STATUS.warning,
  green: STATUS.good,
  teal: "#1a9e8f",
  blue: "#2a78d6",
  violet: "#7b4fd6",
  pink: "#e0679a",
  brown: "#8b5a2b",
} as const;

/** A rampa de cada número de faixas, **do mais alto para o mais baixo** — que é a ordem em que a legenda as lista */
const RAMPS: Record<number, string[]> = {
  1: [PALETTE.blue],
  2: [PALETTE.green, PALETTE.red],
  3: [PALETTE.green, PALETTE.yellow, PALETTE.red],
  4: [PALETTE.blue, PALETTE.green, PALETTE.yellow, PALETTE.red],
  5: [PALETTE.violet, PALETTE.blue, PALETTE.green, PALETTE.yellow, PALETTE.red],
};

export const MAX_BANDS = 5;
/** Daí o teto de cortes: `q` cortes abrem `q + 1` faixas */
export const MAX_CUTS = MAX_BANDS - 1;

/** A cor da faixa de índice `band` (0 é a mais **baixa**) numa escada de `bands` faixas */
export const bandColor = (band: number, bands: number): string => {
  const ramp = RAMPS[Math.min(Math.max(bands, 1), MAX_BANDS)] ?? RAMPS[1];
  return ramp[ramp.length - 1 - band] ?? ramp[ramp.length - 1];
};

/** AS CORES ESCOLHIDAS PELO USUÁRIO ================================= A rampa acima continua sendo o padrão; o que vem daqui a sobrepõe posição a posição */
const COLOR_KEY = "leilao:band-colors";

type BandColors = Record<string, (string | undefined)[]>;

/** Lê o mapa inteiro */
export function readBandColors(): BandColors {
  try {
    const raw = window.localStorage.getItem(COLOR_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed as Record<string, unknown>)
        .filter(([, value]) => Array.isArray(value))
        .map(([axis, value]) => [
          axis,
          (value as unknown[]).map((color) =>
            typeof color === "string" && /^#[0-9a-fA-F]{6}$/.test(color)
              ? color
              : undefined
          ),
        ])
    );
  } catch {
    return {};
  }
}

export function writeBandColor(
  axis: string,
  band: number,
  color: string | null
): BandColors {
  const all = readBandColors();
  const colors = [...(all[axis] ?? [])];
  while (colors.length <= band) colors.push(undefined);
  colors[band] = color ?? undefined;
  const next = { ...all, [axis]: colors };
  try {
    window.localStorage.setItem(COLOR_KEY, JSON.stringify(next));
  } catch {
  }
  return next;
}
