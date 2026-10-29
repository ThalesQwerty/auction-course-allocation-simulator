/** Gerador pseudoaleatório de 32 bits, de semente explícita.
 *
 * A prévia precisa ser **função dos parâmetros**: com `Math.random` o desenho
 * mudaria sozinho a cada render, e o usuário veria ruído onde devia ver o
 * efeito do que acabou de digitar.
 *
 * Não é o gerador do motor (lá é o do numpy, e o que se compara entre os dois
 * é a *forma* da distribuição, não a amostra).
 */
export function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
