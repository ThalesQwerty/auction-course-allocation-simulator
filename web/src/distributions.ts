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
  lognormalDensity,
  lognormalQuantile,
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

/** Onde o eixo da prévia do interesse termina: o percentil 95 da fonte. Sem
 * máximo, o topo é escolha de quem desenha, e um quantil mais alto espremeria a
 * moda contra o zero — a cauda da log-normal cresce depressa com σ. */
const INTEREST_TOP = 0.95;

/** A curva da **log-normal fonte** do interesse, antes da normalização:
 *
 *     x = exp(μ + A + σ·Z),   Z ~ N(0, 1)
 *
 * É a distribuição de onde o motor sorteia (`behavior.draw_interest`), numa
 * disciplina de atratividade `attractiveness`. Forma fechada, como a da
 * disponibilidade: sem amostragem, e por isso a curva não treme enquanto se
 * digita.
 *
 * **É a fonte, não o interesse normalizado.** A normalização divide a linha
 * pelo somatório e com isso apaga μ — o fator e^μ é comum à linha toda —, de
 * modo que μ não muda alocação nenhuma. Ele existe para esta prévia: em μ = 0
 * a massa se espreme entre 0 e 1 e a forma não se lê. O que σ faz aparece aqui
 * do mesmo jeito que na linha normalizada: grande concentra, pequeno achata.
 *
 * A `attractiveness` é o **recorte** que se olha, como a dificuldade é na
 * prévia das notas: a curva é a de uma disciplina com aquela atratividade.
 * Não é parâmetro de cenário — lá ela é declarada por disciplina. Ela se soma
 * a μ no expoente, então desloca a curva inteira; campo vazio vira 0, o
 * neutro.
 *
 * **A estabilidade não entra**: ela reparte a variância entre a peça
 * permanente e a do semestre, e a soma das duas é sempre σ², de modo que a
 * distribuição de um período qualquer não depende dela.
 *
 * Substitui, em 04/11/2026, a prévia em **interesse relativo** (a fração
 * vezes |disciplinas|, sorteada linha a linha): ela é invariante a μ por
 * construção, e mostrar μ foi o motivo de abri-lo ao cenário.
 */
export function interestCurve(scenario: Scenario, attractiveness = 0): Curve {
  const logMean = scenario.interest_mean + attractiveness;
  const logSd = scenario.interest_sigma;
  if (!(logSd > 0) || !Number.isFinite(logMean)) return { points: [], mode: 0 };

  const top = lognormalQuantile(INTEREST_TOP, logMean, logSd);
  const { xs, ys } = lognormalDensity(logMean, logSd, top);
  // A moda tem forma fechada, e ela vence a do grid: o rodapé dá um número,
  // e o grid o arredondaria à largura de um passo.
  return { ...densityCurve(xs, ys), mode: Math.exp(logMean - logSd * logSd) };
}
