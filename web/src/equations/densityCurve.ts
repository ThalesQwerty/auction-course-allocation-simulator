/** Fecha uma curva como **densidade de probabilidade**: a área sob ela vale 1.
 *
 *     área = Σ_i (y_i + y_{i−1})/2 · (x_i − x_{i−1})      trapézio
 *     f_i  = y_i / área
 *     F_i  = F_{i−1} + (f_i + f_{i−1})/2 · (x_i − x_{i−1}) acumulada
 *
 * O trapézio é de **passo variável**: o grid não é uniforme quando a régua é
 * mais larga que o suporte, e aí os pontos se concentram onde a massa está.
 *
 * A acumulada vai junto porque é a única leitura de probabilidade que uma
 * densidade dá num ponto só — a altura de uma densidade não se lê, e é ela
 * que o tooltip mostra. A moda vem de graça na mesma varredura.
 *
 * A densidade pode passar de 1 quando o eixo x é estreito; a probabilidade
 * inteira continua no acumulado.
 */
export interface DensityPoint {
  x: number;
  y: number;
  /** Massa acumulada até aqui — o percentil do ponto. */
  cum: number;
}

export interface Curve {
  points: DensityPoint[];
  /** Onde a densidade é máxima — o valor mais provável. */
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
