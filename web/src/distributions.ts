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
  attemptRates,
  availabilityShape,
  densityCurve,
  gradeDensity,
  gradeShape,
  gradeSds,
  kernelSmooth,
  lognormalDensity,
  lognormalQuantile,
  relativeUtilitySample,
} from "./equations";
import type { Curve } from "./equations";
import type { PerformanceProfile, Profile, Scenario } from "./types";

export type { Curve, DensityPoint } from "./equations";

/** O caso que a prévia das notas desenha: uma disciplina de uma dada
 * dificuldade, numa dada tentativa. Não é parâmetro de cenário — é o recorte
 * que se escolhe para olhar, e por isso vive na tela e não em `Scenario`. */
export interface GradeCase {
  difficulty: number;
  attempt: number;
}

/** O que a prévia das notas tem a dizer de um perfil num dado recorte: a
 * curva, a aprovação que ela implica e as duas chances de ponta já
 * transformadas pela dificuldade e pela tentativa.
 *
 * As chances voltam porque **mudam com o recorte**: as do perfil valem para
 * dificuldade 1 na primeira tentativa, e é a transformação que diz quanto
 * aquela disciplina reprova de fato. `null` é a trinca que não existe. */
export type GradePreview =
  | (Curve & {
      approval: number;
      zeroRate: number;
      maxRate: number;
      mode: number;
    })
  | null;

/** A curva das notas de uma disciplina de uma dada dificuldade, na tentativa
 * escolhida, sobre a escala inteira de 0 a 10.
 *
 * A dificuldade e a tentativa transformam as duas chances de ponta, e a forma
 * é refeita com a **moda do perfil mantida** — é a distribuição que se move
 * sob o aluno, não o aluno sob ela.
 */
export function gradeCurve(
  scenario: Scenario,
  { difficulty, attempt }: GradeCase,
  profile: PerformanceProfile
): GradePreview {
  const base = gradeShape(
    profile.mode_grade,
    profile.zero_rate,
    profile.max_rate
  );
  if (!base) return null;
  const [mode] = base;
  const [zeroRate, maxRate] = attemptRates(
    profile.zero_rate,
    profile.max_rate,
    difficulty,
    attempt
  );
  const [leftSd, rightSd] = gradeSds(mode, zeroRate, maxRate);
  const { xs, ys } = gradeDensity(mode, leftSd, rightSd);
  return {
    ...densityCurve(xs, ys),
    approval: approvalShare(mode, leftSd, rightSd, scenario.min_grade),
    zeroRate,
    maxRate,
    mode,
  };
}

/** A curva da **disponibilidade** de um perfil: as horas que o aluno tem para
 * o período.
 *
 * É a log-normal do perfil sem transformação nenhuma — ao contrário da nota,
 * cuja distribuição se move com a dificuldade e a tentativa. Por isso não há
 * recorte a escolher aqui: a curva é o próprio parâmetro.
 *
 * O eixo **passa de W_a** de propósito: a massa à direita da carga máxima é
 * justamente a chance de alcançá-la, que é um dos dois parâmetros do perfil.
 * Esconder essa parte faria a curva parecer truncada no teto, que é exatamente
 * o que o modelo deixou de fazer.
 *
 * `null` é a combinação que não descreve curva nenhuma — na prática, a moda em
 * cima ou acima de W_a.
 */
export function availabilityCurve(
  profile: Profile,
  maxHours: number
): (Curve & { fullLoad: number; top: number }) | null {
  const shape = availabilityShape(
    profile.mode_hours,
    profile.full_load_rate,
    maxHours
  );
  if (!shape) return null;
  const [logMean, logSd] = shape;
  // Sem máximo, o topo do eixo é escolha de quem desenha: o percentil 99,
  // esticado até caber W_a com folga, para que a linha da carga máxima apareça
  // sempre — mesmo nos perfis apertados, cuja cauda morre antes dela.
  const top = Math.max(lognormalQuantile(0.99, logMean, logSd), maxHours * 1.1);
  const { xs, ys } = lognormalDensity(logMean, logSd, top);
  return {
    ...densityCurve(xs, ys),
    fullLoad: profile.full_load_rate,
    top,
  };
}

/** Quantos pontos a curva da utilidade leva para a tela. */
const CURVE_POINTS = 120;

/** Células do grid fino em que a amostra é contada antes de ser suavizada. */
const FINE_CELLS = 600;

/** Largura do núcleo gaussiano, em células do grid fino. */
const KERNEL_CELLS = 10;

/** A curva de como um aluno reparte a preferência, em **utilidade relativa**:
 * a fração vezes o número de disciplinas, de modo que 1 é a indiferença e a
 * média é exatamente 1 em qualquer cenário. O eixo vai de 0 ao maior valor
 * sorteado — é o suporte da distribuição, e é ele que uma densidade desenha.
 *
 * A `attractiveness` é o **recorte** que se olha, como a dificuldade é na
 * prévia das notas: a curva é a de uma disciplina com aquela atratividade,
 * quando as demais estão em 0. Não é parâmetro de cenário — lá ela é
 * declarada por disciplina. Campo vazio vira 0, que agora é justamente o
 * neutro.
 *
 * A régua da **fração** saiu em 30/10/2026: ela mede a mesma distribuição
 * dividida por |disciplinas|, e com isso o eixo x encolhia na mesma
 * proporção — numa grade de 60 a massa inteira cabia em 4% do eixo e a
 * densidade subia a 100, o que não se lê.
 */
export function utilityCurve(scenario: Scenario, attractiveness = 0): Curve {
  const size = scenario.disciplines.length;
  if (size < 2) return { points: [], mode: 0 };

  const values = relativeUtilitySample(size, scenario.utility_sigma, attractiveness);
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
