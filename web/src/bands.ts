/** As séries da comparação, recorte a recorte: de onde vêm e com que cor saem */
import type { SeriesGroupStyle } from "./charts";
import { bandColor } from "./profileColors";
import type { CutAxis } from "./types";

/** Como o eixo X da série por período se lê */
export const PERIOD_POINT = (x: number) => `Período ${x}`;

/** As grandezas de vida inteira que podem ir ao eixo X da dispersão */
export const SCATTER_AXES: {
  key: "grade_average" | "reserve";
  label: string;
  bounds: [number, number];
   /** Como o valor do eixo se escreve no tooltip */
  format: (value: number) => string;
}[] = [
  {
    key: "grade_average",
    label: "CR final",
    bounds: [0, 10],
    format: (value) =>
      value.toLocaleString("pt-BR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }),
  },
  {
    key: "reserve",
    label: "Utilidade de reserva",
    bounds: [0, 1],
    format: (value) =>
      value.toLocaleString("pt-BR", {
        minimumFractionDigits: 3,
        maximumFractionDigits: 3,
      }),
  },
];

/** O eixo X de uma métrica: o período ou uma grandeza de vida inteira do aluno */
export type AxisChoice = "period" | "grade_average" | "reserve";

/** O que o seletor de linhas oferece */
export type CutChoice = CutAxis;

/** Os recortes na ordem do seletor, com o rótulo da tela, o campo de cortes do cenário e o domínio em que esses cortes valem */
export const CUTS: {
  axis: CutChoice;
  label: string;
  field?: "grade_cuts" | "reserve_cuts";
  domain?: [number, number];
  decimals?: number;
  step?: number;
}[] = [
  { axis: "overall", label: "Geral" },
  {
    axis: "grade_average",
    label: "CR",
    field: "grade_cuts",
    domain: [0, 10],
    decimals: 1,
    step: 0.1,
  },
  {
    axis: "reserve",
    label: "Utilidade de reserva",
    field: "reserve_cuts",
    domain: [0, 1],
    decimals: 3,
    step: 0.001,
  },
];

/** O domínio em que os cortes de um eixo valem */
export function cutDomain(axis: CutChoice): [number, number] | null {
  return CUTS.find((option) => option.axis === axis)?.domain ?? null;
}

/** Os cortes de um eixo valem se caem dentro do domínio e são distintos */
export function validCuts(axis: CutChoice, values: number[]): boolean {
  const domain = cutDomain(axis);
  if (!domain) return true;
  const [low, high] = domain;
  return (
    values.every(
      (value) => Number.isFinite(value) && value > low && value < high
    ) && new Set(values).size === values.length
  );
}

export function cutGroups(
  cut: CutAxis,
  present: string[],
  palette: { solo: string; bands?: (string | undefined)[] }
): SeriesGroupStyle[] {
  if (cut === "overall") {
    return [{ key: "overall", label: "Geral", color: palette.solo }];
  }
  const bands = Math.max(present.length, 1);
  return present.map((key, index) => ({
    key,
    label: key,
    color: palette.bands?.[index] ?? bandColor(index, bands),
  }));
}
