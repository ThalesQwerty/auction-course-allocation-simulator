/** A média da normal dividida.
 *
 *     μ = m + √(2/π) · (d − e)
 *
 * A moda é a locação, mas não é a média: cauda esquerda mais longa (`e > d`)
 * puxa a média para **baixo** da moda, que é o formato de distribuição de
 * nota. O espelho de `equations.split_normal_mean`.
 */
const HALF_NORMAL_MEAN = Math.sqrt(2 / Math.PI);

export function splitNormalMean(
  mode: number,
  leftSd: number,
  rightSd: number
): number {
  return mode + HALF_NORMAL_MEAN * (rightSd - leftSd);
}
