import { useEffect, useState } from "react";

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

export const INK = {
  light: {
    muted: "#898781",
    secondary: "#52514e",
    grid: "#e1e0d9",
    axis: "#c3c2b7",
    surface: "#ffffff",
  },
  dark: {
    muted: "#898781",
    secondary: "#c3c2b7",
    grid: "#2f2f2c",
    axis: "#3b3a36",
    surface: "#262624",
  },
};

export type Ink = (typeof INK)["light"];

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

export const inkFor = (dark: boolean): Ink => INK[dark ? "dark" : "light"];

/** A matiz única das séries solitárias — histograma e curva de densidade. */
export const soloColor = (dark: boolean): string =>
  (dark ? PALETTE_DARK : PALETTE_LIGHT)[0];

export function categoricalColors(
  labels: string[],
  dark: boolean
): Record<string, string> {
  const palette = dark ? PALETTE_DARK : PALETTE_LIGHT;
  return Object.fromEntries(
    labels.map((label, i) => [label, palette[i % palette.length]])
  );
}

/** Paleta de **estado**, fixa nos dois temas e deliberadamente fora da
 * categórica: ela diz se algo passa ou não passa, nunca "qual série é esta".
 * Como a amarela fica abaixo de 3:1 na superfície clara, toda leitura que a
 * use precisa vir com rótulo em palavras ao lado — é a mitigação prevista, e
 * por isso o gráfico colorido por estado exige legenda. */
export const STATUS = { good: "#0ca30c", warning: "#fab219", critical: "#d03b3b" };
