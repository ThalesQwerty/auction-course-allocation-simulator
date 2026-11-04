/** Φ e Φ⁻¹ da normal padrão — os dois primitivos de que a normal dividida vive.
 *
 * O JavaScript não traz nenhum dos dois, e o Python traz (`math.erfc` e
 * `statistics.NormalDist.inv_cdf`). Para a prévia não mentir sobre o que o
 * motor vai produzir, as duas implementações têm de concordar bem além do que
 * a tela mostra: a inversão da forma resolve a partir de probabilidades da
 * ordem de 10⁻⁴, e um Φ⁻¹ de precisão baixa erraria a cauda em dezenas por
 * cento mesmo parecendo certo no meio.
 *
 * Φ sai do `erfc` de Chebyshev (Numerical Recipes), com erro relativo da ordem
 * de 10⁻¹⁵ inclusive na cauda. Φ⁻¹ sai da aproximação racional de Acklam
 * (~10⁻⁹) e um passo de Halley usando Φ, que a leva ao limite do `double`.
 *
 * Privado de propósito: são ferramenta numérica, não conta do modelo.
 */

const CHEBYSHEV = [
  -1.3026537197817094, 6.419697923564902e-1, 1.9476473204185836e-2,
  -9.561514786808631e-3, -9.46595344482036e-4, 3.66839497852761e-4,
  4.2523324806907e-5, -2.0278578112534e-5, -1.624290004647e-6,
  1.30365583558e-6, 1.5626441722e-8, -8.5238095915e-8, 6.529054439e-9,
  5.059343495e-9, -9.91364156e-10, -2.27365122e-10, 9.6467911e-11,
  2.394038e-12, -6.886027e-12, 8.94487e-13, 3.13092e-13, -1.12708e-13,
  3.81e-16, 7.106e-15,
];

function erfcPositive(value: number): number {
  const t = 2 / (2 + value);
  const ty = 4 * t - 2;
  let d = 0;
  let dd = 0;
  for (let j = CHEBYSHEV.length - 1; j > 0; j--) {
    const previous = d;
    d = ty * d - dd + CHEBYSHEV[j];
    dd = previous;
  }
  return t * Math.exp(-value * value + 0.5 * (CHEBYSHEV[0] + ty * d) - dd);
}

export function standardNormalCdf(value: number): number {
  const scaled = -value / Math.SQRT2;
  return 0.5 * (scaled >= 0 ? erfcPositive(scaled) : 2 - erfcPositive(-scaled));
}

const A = [
  -3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2,
  1.38357751867269e2, -3.066479806614716e1, 2.506628277459239,
];
const B = [
  -5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2,
  6.680131188771972e1, -1.328068155288572e1,
];
const C = [
  -7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838,
  -2.549732539343734, 4.374664141464968, 2.938163982698783,
];
const D = [
  7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996,
  3.754408661907416,
];
const LOW = 0.02425;

export function standardNormalQuantile(probability: number): number {
  if (!(probability > 0) || !(probability < 1)) {
    return probability <= 0 ? -Infinity : Infinity;
  }
  let guess: number;
  if (probability < LOW) {
    const q = Math.sqrt(-2 * Math.log(probability));
    guess =
      (((((C[0] * q + C[1]) * q + C[2]) * q + C[3]) * q + C[4]) * q + C[5]) /
      ((((D[0] * q + D[1]) * q + D[2]) * q + D[3]) * q + 1);
  } else if (probability > 1 - LOW) {
    const q = Math.sqrt(-2 * Math.log(1 - probability));
    guess =
      -(((((C[0] * q + C[1]) * q + C[2]) * q + C[3]) * q + C[4]) * q + C[5]) /
      ((((D[0] * q + D[1]) * q + D[2]) * q + D[3]) * q + 1);
  } else {
    const q = probability - 0.5;
    const r = q * q;
    guess =
      ((((((A[0] * r + A[1]) * r + A[2]) * r + A[3]) * r + A[4]) * r + A[5]) *
        q) /
      (((((B[0] * r + B[1]) * r + B[2]) * r + B[3]) * r + B[4]) * r + 1);
  }
  // Um passo de Halley: o erro de Acklam cai de ~10⁻⁹ para o do `double`.
  const error = standardNormalCdf(guess) - probability;
  const density = Math.exp(-0.5 * guess * guess) / Math.sqrt(2 * Math.PI);
  if (!(density > 0)) return guess;
  const step = error / density;
  return guess - step / (1 + (guess * step) / 2);
}
