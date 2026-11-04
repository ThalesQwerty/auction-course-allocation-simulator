/** Os parâmetros da log-normal da disponibilidade, a partir de moda e chance.
 *
 *     μ = ln(moda) + σ²
 *     σ = (−z + √(z² + 4L)) / 2,   L = ln(teto / moda),  z = Φ⁻¹(1 − p)
 *     teto = W_a − 0,5
 *
 * O espelho de `equations.availability_shape`. Forma fechada: σ é a raiz
 * positiva de `σ² + σz − L = 0`, que é o que resta ao substituir
 * `μ = ln(moda) + σ²` na condição `P(X ≥ teto) = p`.
 *
 * A disponibilidade é a carga que o aluno tem para o período, **em horas**. O
 * teto de carga é do sistema, não do aluno: passar de W_a é legítimo, e quem
 * impede a matrícula é o alocador. A log-normal dá suporte (0, ∞) — nunca
 * negativa, sem máximo artificial.
 *
 * O limiar é o da carga **arredondada** (`W_a − 0,5`), e não o da carga cheia:
 * a carga efetiva é `round(δ)`, então meia hora abaixo de W_a já a alcança.
 * Casar a inversão com ele é o que faz a chance declarada ser a realizada.
 *
 * A única exigência é **moda < W_a − 0,5**: com o pico no teto, `L ≤ 0` e a
 * raiz não existe. `null` é a combinação que não descreve curva nenhuma.
 */
import { standardNormalQuantile } from "./_standardNormal";

/** O limiar da carga cheia: `W_a − 0,5`. Como a carga efetiva é `round(δ)`,
 * meia hora abaixo do teto já o alcança — é nesse ponto, e não em W_a, que quem
 * precisaria excluir disciplina passa a encher a carga. */
export const fullLoadThreshold = (maxHours: number): number => maxHours - 0.5;

export function availabilityShape(
  modeHours: number,
  fullLoadRate: number,
  maxHours: number
): [logMean: number, logSd: number] | null {
  if (!(modeHours > 0) || !(maxHours > 0)) return null;
  if (!(fullLoadRate > 0 && fullLoadRate < 1)) return null;
  const threshold = fullLoadThreshold(maxHours);
  if (modeHours >= threshold) return null;
  const span = Math.log(threshold / modeHours);
  const z = standardNormalQuantile(1 - fullLoadRate);
  const logSd = 0.5 * (-z + Math.sqrt(z * z + 4 * span));
  return [Math.log(modeHours) + logSd * logSd, logSd];
}
