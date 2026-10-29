/** Os parâmetros de forma da Beta da aptidão, a partir de média e concentração.
 *
 *     forma₁ = média · concentração
 *     forma₂ = (1 − média) · concentração
 *
 * A mesma conversão que o motor faz na entrada (`equations.aptitude_shape`).
 * Ela é duplicada aqui de propósito: a prévia precisa do número **antes** de
 * existir execução a quem perguntar.
 */
export function betaShape(
  mean: number,
  concentration: number
): [alpha: number, beta: number] {
  return [mean * concentration, (1 - mean) * concentration];
}
