/** A régua vertical de um gráfico de comparação */
import { niceScale } from "./niceScale";

/** Folga mínima para uma amostra sem dispersão: sem ela a marca fica colada no eixo */
const FLAT = 0.01;

export interface Scale {
  from: number;
  to: number;
  ticks: number[];
}

export function paddedScale(
  values: number[],
  {
    bounds,
    zeroLine = false,
    padding,
  }: { bounds?: [number, number]; zeroLine?: boolean; padding: number }
): Scale {
  if (bounds && Number.isFinite(bounds[0]) && Number.isFinite(bounds[1])) {
    const [from, to] = bounds;
    return {
      from,
      to,
      ticks: niceScale(from, to).ticks.filter(
        (tick) => tick >= from - 1e-9 && tick <= to + 1e-9
      ),
    };
  }

  if (!values.length) return { from: 0, to: 1, ticks: [0, 1] };

  let low = Math.min(...values);
  let high = Math.max(...values);
  if (zeroLine) {
    low = Math.min(low, 0);
    high = Math.max(high, 0);
  }
  const pad = (high - low) * padding || Math.max(Math.abs(high) * 0.05, FLAT);
  const nice = niceScale(low - pad, high + pad);
  return bounds
    ? { ...nice, from: Math.max(nice.from, bounds[0]), to: Math.min(nice.to, bounds[1]) }
    : nice;
}
