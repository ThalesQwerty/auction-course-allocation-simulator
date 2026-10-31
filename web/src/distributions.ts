/** Prévia das duas distribuições de entrada, calculada no navegador enquanto
 * o usuário edita os parâmetros.
 *
 * Aqui não há dados: o que a tela desenha é a **forma que os parâmetros
 * produzem**, antes de existir execução alguma. Por isso são curvas de
 * densidade, e não os histogramas do resultado — lá as barras contam o que de
 * fato aconteceu.
 *
 * As contas estão em `equations/`; este módulo só as encadeia e devolve o que
 * o gráfico consome.
 */
import {
  approvalShare,
  betaShape,
  densityCurve,
  gradeDensity,
  gradeExponent,
  kernelSmooth,
  relativeUtilitySample,
} from "./equations";
import type { Curve } from "./equations";
import type { Scenario } from "./types";

export type { Curve, DensityPoint } from "./equations";

/** O caso que a prévia das notas desenha: uma disciplina de uma dada
 * dificuldade, numa dada tentativa. Não é parâmetro de cenário — é o recorte
 * que se
 * escolhe para olhar, e por isso vive na tela e não em `Scenario`. */
export interface GradeCase {
  difficulty: number;
  attempt: number;
  /** A fração de utilidade vezes o número de disciplinas, de modo que 1 é o
   * aluno indiferente e 2 é querer o dobro da média. Só morde quando o ganho
   * por utilidade do cenário é maior que zero, porque é como expoente dele
   * que ela entra. */
  relativeUtility: number;
}

/** A curva das notas de uma disciplina de uma dada dificuldade, na tentativa
 * escolhida, sobre a escala inteira de 0 a 10.
 *
 * Curva para a forma, quadratura para o número: a **aprovação** não sai da
 * curva, porque a quadratura integra certo mesmo onde a densidade diverge na
 * ponta.
 */
export function gradeCurve(
  scenario: Scenario,
  { difficulty, attempt, relativeUtility }: GradeCase
): Curve & { approval: number } {
  const [alpha, beta] = betaShape(
    scenario.aptitude_mean,
    scenario.aptitude_concentration
  );
  const exponent = gradeExponent({
    difficulty,
    attempt,
    relativeUtility,
    utilityGain: scenario.utility_gain,
    retakeGain: scenario.retake_gain,
  });
  const { xs, ys } = gradeDensity(alpha, beta, exponent);
  return {
    ...densityCurve(xs, ys),
    approval: approvalShare(alpha, beta, exponent, scenario.min_grade),
  };
}

/** Quantos pontos a curva da utilidade leva para a tela. */
const CURVE_POINTS = 120;

/** Células do grid fino em que a amostra é contada antes de ser suavizada. */
const FINE_CELLS = 600;

/** Largura do núcleo gaussiano, em células do grid fino. */
const KERNEL_CELLS = 10;

/** Campo vazio vira 0, e atratividade 0 zeraria a linha inteira. */
const MIN_ATTRACTIVENESS = 0.1;

/** A curva de como um aluno reparte a preferência, em **utilidade relativa**:
 * a fração vezes o número de disciplinas, de modo que 1 é a indiferença e a
 * média é exatamente 1 em qualquer cenário. O eixo vai de 0 ao maior valor
 * sorteado — é o suporte da distribuição, e é ele que uma densidade desenha.
 *
 * A `attractiveness` é o **recorte** que se olha, como a dificuldade é na
 * prévia das notas: a curva é a de uma disciplina com aquela atratividade,
 * quando as demais estão em 1. Não é parâmetro de cenário — lá ela é
 * declarada por disciplina.
 *
 * A régua da **fração** saiu em 30/10/2026: ela mede a mesma distribuição
 * dividida por |disciplinas|, e com isso o eixo x encolhia na mesma
 * proporção — numa grade de 60 a massa inteira cabia em 4% do eixo e a
 * densidade subia a 100, o que não se lê.
 */
export function utilityCurve(scenario: Scenario, attractiveness = 1): Curve {
  const size = scenario.disciplines.length;
  if (size < 2) return { points: [], mode: 0 };

  const values = relativeUtilitySample(
    size,
    scenario.utility_sigma,
    attractiveness > 0 ? attractiveness : MIN_ATTRACTIVENESS
  );
  const highest = values.reduce((max, value) => Math.max(max, value), 0);
  if (!(highest > 0)) return { points: [], mode: 0 };

  const counts = new Array<number>(FINE_CELLS).fill(0);
  for (const value of values) {
    const cell = Math.floor((value / highest) * FINE_CELLS);
    counts[Math.min(FINE_CELLS - 1, Math.max(0, cell))] += 1;
  }
  const smooth = kernelSmooth(counts, KERNEL_CELLS);

  // O grid fino desce para os pontos da curva, e a área vai a 1 na saída.
  const xs: number[] = [];
  const ys: number[] = [];
  for (let i = 0; i < CURVE_POINTS; i++) {
    const part = i / (CURVE_POINTS - 1);
    xs.push(highest * part);
    ys.push(smooth[Math.min(FINE_CELLS - 1, Math.round(part * (FINE_CELLS - 1)))]);
  }
  return densityCurve(xs, ys);
}
