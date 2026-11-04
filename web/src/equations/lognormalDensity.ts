/** A densidade da log-normal num grid.
 *
 *     f(x) = 1 / (x·σ·√(2π)) · exp(−(ln x − μ)² / (2σ²)),   x > 0
 *
 * Forma fechada, como a da nota: sem amostragem, sem suavização, e por isso a
 * curva não treme enquanto se digita.
 *
 * O eixo x está na unidade de quem chama: **carga horária** na prévia da
 * disponibilidade, que é a unidade em que a exclusão se pensa, e a escala crua
 * do sorteio na prévia do interesse. A curva fecha no zero pela esquerda,
 * porque a log-normal nunca é negativa.
 *
 * `top` é onde o eixo termina. Quem chama escolhe, porque não há máximo: o
 * natural é um quantil alto. Na disponibilidade ele é esticado até W_a quando
 * o perfil é apertado, para que a linha da carga máxima apareça sempre — a
 * massa à direita dela é justamente a chance de alcançá-la.
 */
const POINTS = 161;

export function lognormalDensity(
  logMean: number,
  logSd: number,
  top: number
): { xs: number[]; ys: number[] } {
  const xs: number[] = [];
  const ys: number[] = [];
  const step = top / (POINTS - 1);
  for (let i = 0; i < POINTS; i++) {
    const hours = i * step;
    xs.push(hours);
    if (hours <= 0) {
      ys.push(0);
      continue;
    }
    const z = (Math.log(hours) - logMean) / logSd;
    ys.push(
      Math.exp(-0.5 * z * z) / (hours * logSd * Math.sqrt(2 * Math.PI))
    );
  }
  return { xs, ys };
}
