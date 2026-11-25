/** Os parâmetros da log-normal da disponibilidade, a partir de moda e chance */
import { standardNormalQuantile } from "./_standardNormal";

/** O limiar da carga cheia: `W_a − 0,5` */
export const fullLoadThreshold = (maxHours: number): number => maxHours - 0.5;

export function availabilityShape(
  modeHours: number,
  fullLoadRate: number,
  maxHours: number
): [logMean: number, logSd: number] | null {
  if (!(modeHours > 0) || !(maxHours > 0)) return null;
  if (!(fullLoadRate > 0 && fullLoadRate < 1)) return null;
  const threshold = fullLoadThreshold(maxHours);
  if (modeHours >= threshold) return null;
  const span = Math.log(threshold / modeHours);
  const z = standardNormalQuantile(1 - fullLoadRate);
  const logSd = 0.5 * (-z + Math.sqrt(z * z + 4 * span));
  return [Math.log(modeHours) + logSd * logSd, logSd];
}
