/** O quantil da log-normal.
 *
 *     F⁻¹(q) = exp(μ + σ·Φ⁻¹(q))
 *
 * Serve para escolher onde o eixo da prévia termina: como a distribuição não
 * tem máximo, o topo do desenho é uma decisão de quem desenha, e um quantil
 * alto é a escolha que mostra a cauda sem deixar a curva espremida.
 */
import { standardNormalQuantile } from "./_standardNormal";

export function lognormalQuantile(
  probability: number,
  logMean: number,
  logSd: number
): number {
  return Math.exp(logMean + logSd * standardNormalQuantile(probability));
}
