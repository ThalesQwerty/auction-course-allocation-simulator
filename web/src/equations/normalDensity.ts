/** A densidade da normal das notas, amostrada sobre a escala de 0 a 10 */
const POINTS = 241;
const STEP = 10 / (POINTS - 1);
const ROOT_TWO_PI = Math.sqrt(2 * Math.PI);

export function normalDensity(
  mean: number,
  sd: number
): { xs: number[]; ys: number[] } {
  const xs: number[] = [];
  const ys: number[] = [];
  for (let i = 0; i < POINTS; i++) {
    const grade = i * STEP;
    const z = (grade - mean) / sd;
    xs.push(grade);
    ys.push(Math.exp(-0.5 * z * z) / (sd * ROOT_TWO_PI));
  }
  return { xs, ys };
}

/** A massa acima da nota de corte, que é a taxa de aprovação realizada */
export function approvalAbove(
  mean: number,
  sd: number,
  minGrade: number
): number {
  return 0.5 * erfc((minGrade - mean) / sd / Math.SQRT2);
}

function erfc(x: number): number {
  const z = Math.abs(x);
  const t = 1 / (1 + 0.5 * z);
  const y =
    t *
    Math.exp(
      -z * z -
        1.26551223 +
        t *
          (1.00002368 +
            t *
              (0.37409196 +
                t *
                  (0.09678418 +
                    t *
                      (-0.18628806 +
                        t *
                          (0.27886807 +
                            t *
                              (-1.13520398 +
                                t * (1.48851587 + t * (-0.82215223 + t * 0.17087277))))))))
    );
  return x >= 0 ? y : 2 - y;
}
