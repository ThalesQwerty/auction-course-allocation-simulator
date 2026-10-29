/** Suavização por núcleo gaussiano, com reflexão nas bordas.
 *
 *     ŷ_i = Σ_k y_{i+k} · w_k / Σ_k w_k,     w_k = exp(−k² / 2h²)
 *
 * Uma amostra contada num grid fino sai com um serrilhado que parece dado
 * medido. O núcleo é o que a devolve ao que ela é: uma forma, não uma
 * amostra.
 *
 * Nas bordas o núcleo é **refletido** em vez de truncado. Truncar faria a
 * densidade afundar justamente onde a distribuição de utilidade empilha
 * massa, que é encostada no zero — a curva mentiria sobre a moda.
 *
 * O alcance é 3h, onde o peso gaussiano já caiu a ~1% do centro.
 */
const REACH_IN_BANDWIDTHS = 3;

export function kernelSmooth(counts: number[], bandwidth: number): number[] {
  const reach = bandwidth * REACH_IN_BANDWIDTHS;
  const kernel: number[] = [];
  for (let k = -reach; k <= reach; k++) {
    kernel.push(Math.exp((-0.5 * k * k) / (bandwidth * bandwidth)));
  }

  const smooth = new Array<number>(counts.length).fill(0);
  for (let i = 0; i < counts.length; i++) {
    let weighted = 0;
    let mass = 0;
    for (let k = -reach; k <= reach; k++) {
      let j = i + k;
      if (j < 0) j = -j - 1;
      if (j >= counts.length) j = 2 * counts.length - j - 1;
      if (j < 0 || j >= counts.length) continue;
      const w = kernel[k + reach];
      weighted += counts[j] * w;
      mass += w;
    }
    smooth[i] = mass > 0 ? weighted / mass : 0;
  }
  return smooth;
}
