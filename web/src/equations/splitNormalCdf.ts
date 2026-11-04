/** A acumulada da normal dividida.
 *
 *     F(x) = 2e/(e+d) · Φ((x − m)/e),                  x < m
 *     F(x) = e/(e+d) + 2d/(e+d) · (Φ((x − m)/d) − ½),  x ≥ m
 *
 * O espelho de `equations.split_normal_cdf`. Duplicada de propósito: a prévia
 * precisa da forma **antes** de existir execução a quem perguntar.
 */
import { standardNormalCdf } from "./_standardNormal";

export function splitNormalCdf(
  value: number,
  mode: number,
  leftSd: number,
  rightSd: number
): number {
  const leftMass = leftSd / (leftSd + rightSd);
  if (value < mode) {
    return 2 * leftMass * standardNormalCdf((value - mode) / leftSd);
  }
  const rightMass = rightSd / (leftSd + rightSd);
  return (
    leftMass + 2 * rightMass * (standardNormalCdf((value - mode) / rightSd) - 0.5)
  );
}
