/** A fração da população que alcança a nota mínima.
 *
 *     P(n ≥ n_min) = P( a ≥ (n_min/10)^(1/E) )
 *
 * A nota é monótona na aptidão, então aprovar é ter aptidão acima de um
 * limiar — e a conta vira uma integral da Beta, feita pela quadratura.
 *
 * Ela **não sai da curva** de `gradeDensity`: curva para a forma, quadratura
 * para o número. A quadratura integra certo mesmo quando a densidade diverge
 * na ponta, que é onde a curva erraria.
 */
import { betaQuadrature } from "./betaQuadrature";

export function approvalShare(
  alpha: number,
  beta: number,
  exponent: number,
  minGrade: number
): number {
  const target = Math.min(1, Math.max(0, minGrade / 10));
  if (target <= 0) return 1;
  const floor = Math.pow(target, 1 / exponent);
  let share = 0;
  for (const { logA, weight } of betaQuadrature(alpha, beta)) {
    if (Math.exp(logA) >= floor) share += weight;
  }
  return share;
}
