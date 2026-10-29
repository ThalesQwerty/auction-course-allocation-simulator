/** Uma amostra de utilidade relativa, como o motor a produz.
 *
 *     u'_x = exp(σ · Z_x),  Z ~ N(0, 1)        log-normal
 *     u_x  = u'_x / Σ_y u'_y                   normalização da linha
 *     u_rel_x = u_x · |disciplinas|            múltiplos da indiferença
 *
 * Espelha dois dos três passos de `behavior.draw_utilities`. A régua é a
 * **utilidade relativa** — a fração vezes o número de disciplinas, de modo
 * que a média é exatamente 1 em qualquer cenário. A régua da fração saiu
 * porque o eixo encolhia na mesma proporção: numa grade de 60 a massa inteira
 * cabia em 4% do eixo e a densidade subia a 100, o que não se lê.
 *
 * **O deslocamento por altura fica de fora**, e é uma decisão de leitura: ele
 * é curricular, não populacional — ordena as camadas entre si —, e domina
 * tanto a linha que, com ele, metade das disciplinas (as de altura 0) cai
 * sozinha na primeira célula e o desenho não se mexe mais com σ.
 *
 * **A estabilidade também não entra**: ela reparte a variância entre a parte
 * permanente e a do semestre, e a soma das duas é sempre 1, de modo que a
 * distribuição de um período qualquer não depende dela.
 *
 * Esta é a única curva da prévia que vem de sorteio — não há forma fechada
 * para a fração `x/Σx`.
 */
import { mulberry32 } from "./mulberry32";

/** Linhas sorteadas. Bastantes para o núcleo gaussiano ter o que suavizar. */
const ROWS = 480;

/** Semente da prévia. Não é a seed do cenário de propósito: o que a tela
 * mostra é a forma que os parâmetros produzem, não a execução que virá. */
const SEED = 20261029;

export function relativeUtilitySample(size: number, sigma: number): number[] {
  const random = mulberry32(SEED);
  const row = new Array<number>(size).fill(0);
  const values = new Array<number>(ROWS * size);
  let at = 0;

  for (let r = 0; r < ROWS; r++) {
    for (let j = 0; j < size; j += 2) {
      // Box-Muller: dois normais independentes por par de uniformes.
      const u1 = Math.max(random(), Number.MIN_VALUE);
      const u2 = random();
      const radius = Math.sqrt(-2 * Math.log(u1));
      row[j] = Math.exp(sigma * radius * Math.cos(2 * Math.PI * u2));
      if (j + 1 < size) {
        row[j + 1] = Math.exp(sigma * radius * Math.sin(2 * Math.PI * u2));
      }
    }
    let sum = 0;
    for (let j = 0; j < size; j++) sum += row[j];
    for (let j = 0; j < size; j++) values[at++] = (row[j] / sum) * size;
  }
  return values;
}
