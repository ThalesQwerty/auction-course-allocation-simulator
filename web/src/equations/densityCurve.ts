/** Fecha uma curva como **densidade de probabilidade**: a área sob ela vale 1 */
export interface DensityPoint {
  x: number;
  y: number;
  cum: number;
}

export interface Curve {
  points: DensityPoint[];
  mode: number;
}

export function densityCurve(xs: number[], ys: number[]): Curve {
  let area = 0;
  for (let i = 1; i < ys.length; i++) {
    area += ((ys[i] + ys[i - 1]) / 2) * (xs[i] - xs[i - 1]);
  }
  if (!(area > 0)) {
    return { points: xs.map((x) => ({ x, y: 0, cum: 0 })), mode: 0 };
  }

  const points: DensityPoint[] = [];
  let cum = 0;
  let mode = 0;
  let highest = -1;
  for (let i = 0; i < ys.length; i++) {
    const density = ys[i] / area;
    if (i > 0) cum += ((density + ys[i - 1] / area) / 2) * (xs[i] - xs[i - 1]);
    if (density > highest) {
      highest = density;
      mode = xs[i];
    }
    points.push({ x: xs[i], y: density, cum: Math.min(1, cum) });
  }
  return { points, mode };
}
