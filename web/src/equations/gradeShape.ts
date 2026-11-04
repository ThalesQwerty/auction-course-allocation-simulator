/** A forma da normal dividida da nota, a partir das três grandezas que se leem.
 *
 *     entra: nota mais provável, chance de tirar 0, chance de tirar 10
 *     sai:   (moda, desvio esquerdo, desvio direito)
 *
 * O espelho de `equations.grade_shape`, inclusive na estratégia: a **moda é a
 * locação**, então entra direto — o número digitado é literalmente o pico da
 * curva —, e a conversão só precisa achar os dois desvios. A chance de zero
 * fixa a cauda esquerda, a de dez fixa a direita, por uma bisseção sem chute
 * inicial.
 *
 * A média sai derivada, 1 a 2 pontos **abaixo** da moda, porque a cauda
 * esquerda é longa. E **toda trinca existe**: não há faixa a recusar, ao
 * contrário do que haveria se o parâmetro fosse a média.
 *
 * Os limiares são os da nota **arredondada** (0,05 e 9,95), não os da escala:
 * é o que faz "chance de tirar 10" significar exatamente isso.
 */
import { standardNormalQuantile } from "./_standardNormal";

export const ZERO_THRESHOLD = 0.05;
export const MAX_THRESHOLD = 9.95;

const BISECTIONS = 200;

export function gradeSds(
  mode: number,
  zeroRate: number,
  maxRate: number
): [leftSd: number, rightSd: number] {
  const sds = (leftMass: number): [number, number] => [
    (mode - ZERO_THRESHOLD) / -standardNormalQuantile(zeroRate / (2 * leftMass)),
    (MAX_THRESHOLD - mode) /
      -standardNormalQuantile(maxRate / (2 * (1 - leftMass))),
  ];
  const margin = (1 - maxRate - zeroRate) * 1e-12;
  let low = zeroRate + margin;
  let high = 1 - maxRate - margin;
  for (let i = 0; i < BISECTIONS; i++) {
    const middle = (low + high) / 2;
    const [left, right] = sds(middle);
    if (left / (left + right) - middle > 0) low = middle;
    else high = middle;
  }
  return sds((low + high) / 2);
}

/** A trinca de forma, ou `null` quando os parâmetros não descrevem curva
 * nenhuma — a moda fora da escala, ou as duas chances que não cabem juntas.
 * Quem chama decide o que dizer, porque a prévia não tem a quem lançar erro. */
export function gradeShape(
  modeGrade: number,
  zeroRate: number,
  maxRate: number
): [mode: number, leftSd: number, rightSd: number] | null {
  if (!(modeGrade > ZERO_THRESHOLD && modeGrade < MAX_THRESHOLD)) return null;
  if (!(zeroRate > 0 && maxRate > 0 && zeroRate + maxRate < 1)) return null;
  const [leftSd, rightSd] = gradeSds(modeGrade, zeroRate, maxRate);
  return [modeGrade, leftSd, rightSd];
}
