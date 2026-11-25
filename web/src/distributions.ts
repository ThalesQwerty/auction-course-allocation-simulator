/** Prévia das duas distribuições de entrada, calculada no navegador enquanto o usuário edita os parâmetros */
import {
  approvalAbove,
  attemptApproval,
  availabilityShape,
  densityCurve,
  gradeMean,
  lognormalDensity,
  lognormalQuantile,
  normalDensity,
} from "./equations";
import type { Curve } from "./equations";
import type { AvailabilityShape, Scenario } from "./types";

export type { Curve, DensityPoint } from "./equations";

/** O que a prévia das notas tem a dizer num dado número de repetições: a curva, a média que a gerou e a aprovação que ela implica */
export type GradePreview =
  | (Curve & {
      approval: number;
      mean: number;
    })
  | null;

/** A curva das notas na tentativa escolhida, sobre a escala inteira de 0 a 10 */
export function gradeCurve(scenario: Scenario, attempt: number): GradePreview {
  const rate = attemptApproval(
    scenario.approval_rate,
    scenario.repetition_gain,
    Math.max(0, Math.round(attempt) - 1)
  );
  const mean = gradeMean(scenario.min_grade, scenario.grade_sd, rate);
  if (mean === null) return null;
  const { xs, ys } = normalDensity(mean, scenario.grade_sd);
  return {
    ...densityCurve(xs, ys),
    approval: approvalAbove(mean, scenario.grade_sd, scenario.min_grade),
    mean,
  };
}

/** A curva da **disponibilidade** de um perfil: as horas que o aluno tem para o período */
export function availabilityCurve(
  profile: AvailabilityShape,
  maxHours: number
): (Curve & { fullLoad: number; top: number }) | null {
  const shape = availabilityShape(
    profile.mode_hours,
    profile.full_load_rate,
    maxHours
  );
  if (!shape) return null;
  const [logMean, logSd] = shape;
  const top = Math.max(lognormalQuantile(0.99, logMean, logSd), maxHours * 1.1);
  const { xs, ys } = lognormalDensity(logMean, logSd, top);
  return {
    ...densityCurve(xs, ys),
    fullLoad: profile.full_load_rate,
    top,
  };
}

/** Onde o eixo da prévia do interesse termina: o percentil 95 da fonte */
const INTEREST_TOP = 0.95;

/** A curva da **log-normal fonte** do interesse, antes da normalização: x = A · exp(μ + σ·Z),   Z ~ N(0, 1) É a distribuição de onde o motor sorteia (`behavior.draw_interest`) */
export function interestCurve(scenario: Scenario): Curve {
  const logMean = scenario.interest_mean;
  const logSd = scenario.interest_sigma;
  if (!(logSd > 0) || !Number.isFinite(logMean)) return { points: [], mode: 0 };

  const top = lognormalQuantile(INTEREST_TOP, logMean, logSd);
  const { xs, ys } = lognormalDensity(logMean, logSd, top);
  return { ...densityCurve(xs, ys), mode: Math.exp(logMean - logSd * logSd) };
}

/** A curva da **seletividade**: a log-normal da opção externa do aluno */
export function selectivityCurve(scenario: Scenario): Curve {
  const median = scenario.selectivity_median;
  const logSd = scenario.selectivity_sigma;
  if (!(median > 0) || !(logSd > 0)) return { points: [], mode: 0 };

  const logMean = Math.log(median);
  const top = lognormalQuantile(INTEREST_TOP, logMean, logSd);
  const { xs, ys } = lognormalDensity(logMean, logSd, top);
  return { ...densityCurve(xs, ys), mode: Math.exp(logMean - logSd * logSd) };
}
