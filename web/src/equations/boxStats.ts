/** O resumo de cinco números de uma amostra, mais os pontos fora dos bigodes.
 *
 *     cerca = 1,5 · (q3 − q1)
 *     bigodes = o valor mais extremo ainda dentro de [q1 − cerca, q3 + cerca]
 *     ponto solto = o que fica fora
 *
 * É a convenção de **Tukey**. Os bigodes não são o mínimo e o máximo: eles
 * param no último dado que ainda está perto do corpo da distribuição, e o que
 * sobra aparece como ponto, que é o que distingue "a amostra é dispersa" de
 * "houve uma execução estranha".
 *
 * Cada valor dentro de uma caixa é uma execução; a comparação entre caixas é
 * a **sobreposição** delas, e não a distância entre as medianas.
 */
import { quantile } from "./quantile";

export interface BoxStats {
  n: number;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  low: number;
  high: number;
  outliers: number[];
}

const FENCE = 1.5;

export function boxStats(values: number[]): BoxStats | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const q1 = quantile(sorted, 0.25);
  const median = quantile(sorted, 0.5);
  const q3 = quantile(sorted, 0.75);
  const fence = FENCE * (q3 - q1);
  const inside = sorted.filter((v) => v >= q1 - fence && v <= q3 + fence);
  return {
    n: sorted.length,
    min: sorted[0],
    q1,
    median,
    q3,
    max: sorted[sorted.length - 1],
    low: inside.length ? inside[0] : sorted[0],
    high: inside.length ? inside[inside.length - 1] : sorted[sorted.length - 1],
    outliers: sorted.filter((v) => v < q1 - fence || v > q3 + fence),
  };
}
