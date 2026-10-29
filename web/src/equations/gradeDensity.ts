/** A densidade da nota, em forma fechada.
 *
 *     n = 10 · a^E   ⟹   a = (n/10)^(1/E)
 *     f_n(n) = f_a(a) · |da/dn| = f_a(a) · a / (10·E·(n/10))
 *
 * A nota é **monótona** na aptidão e nada mais é sorteado, então a densidade
 * sai por mudança de variável — nada de amostragem, nada de faixas, e a curva
 * é lisa por construção: ela não treme a cada tecla.
 *
 * As pontas fecham no eixo: a nota 0 e a nota 10 só ocorrem no limite, e é lá
 * que a densidade pode divergir.
 *
 * Em t > 1 o que sai é a nota que a **população inteira** tiraria naquela
 * tentativa, e não a dos recursantes: quem recursa é quem foi mal, então a
 * amostra real de uma segunda tentativa é a cauda de baixo da aptidão. Isto
 * responde "quanto a tentativa vale", não "como ficou a turma de repetentes".
 */

/** A curva anda de **um décimo**, que é a grade em que o motor entrega a nota
 * (`round(100 · a^E)/10`). Assim todo ponto do desenho é uma nota que a
 * simulação pode de fato produzir. */
const POINTS = 101;
const TOP = 10;

export function gradeDensity(
  alpha: number,
  beta: number,
  exponent: number
): { xs: number[]; ys: number[] } {
  const step = TOP / (POINTS - 1);
  const xs: number[] = [];
  const ys: number[] = [];
  for (let i = 0; i < POINTS; i++) {
    const n = i * step;
    xs.push(n);
    const t = n / TOP;
    if (t <= 0 || t >= 1) {
      ys.push(0);
      continue;
    }
    const a = Math.pow(t, 1 / exponent);
    if (!(a > 0) || a >= 1) {
      ys.push(0);
      continue;
    }
    // Densidade da Beta vezes o jacobiano. A constante B(α, β) some na
    // normalização numérica de quem consome a curva.
    ys.push(
      Math.exp((alpha - 1) * Math.log(a) + (beta - 1) * Math.log(1 - a)) *
        (a / (TOP * exponent * t))
    );
  }
  return { xs, ys };
}
