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
  const { xs, ys } = normalDensity(mean, scenario.grade_sd, 10);
  return {
    ...densityCurve(xs, ys),
    approval: approvalAbove(mean, scenario.grade_sd, scenario.min_grade),
    mean,
  };
}

/** A curva da **disponibilidade**: as horas que o aluno tem para o período, presas em [0, W_a] */
export function availabilityCurve(
  profile: AvailabilityShape,
  maxHours: number
): (Curve & { fullLoad: number; mean: number }) | null {
  const shape = availabilityShape(
    profile.hours_sd,
    profile.full_load_rate,
    maxHours
  );
  if (!shape) return null;
  const [mean, sd] = shape;
  const { xs, ys } = normalDensity(mean, sd, maxHours);
  return {
    ...densityCurve(xs, ys),
    fullLoad: profile.full_load_rate,
    mean,
  };
}

/** Onde o eixo da prévia do interesse termina: o percentil 95 da fonte */
const INTEREST_TOP = 0.95;

/** A curva de uma **log-normal fonte**: x = exp(μ + σ·Z),   Z ~ N(0, 1) */
function sourceCurve(logMean: number, logSd: number): Curve {
  if (!(logSd > 0) || !Number.isFinite(logMean)) return { points: [], mode: 0 };
  const top = lognormalQuantile(INTEREST_TOP, logMean, logSd);
  const { xs, ys } = lognormalDensity(logMean, logSd, top);
  return { ...densityCurve(xs, ys), mode: Math.exp(logMean - logSd * logSd) };
}

/** A fonte do interesse por **disciplina** (`behavior.draw_interest`) */
export const interestCurve = (scenario: Scenario): Curve =>
  sourceCurve(scenario.interest_mean, scenario.interest_sigma);

/** A fonte do interesse por **horário** (`behavior.draw_schedule_interest`) */
export const scheduleCurve = (scenario: Scenario): Curve =>
  sourceCurve(scenario.schedule_mean, scenario.schedule_sigma);

/** A fonte da **seletividade**: a log-normal da opção externa do aluno */
export const selectivityCurve = (scenario: Scenario): Curve =>
  sourceCurve(scenario.selectivity_mean, scenario.selectivity_sigma);
