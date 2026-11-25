/** O quantil da log-normal */
import { standardNormalQuantile } from "./_standardNormal";

export function lognormalQuantile(
  probability: number,
  logMean: number,
  logSd: number
): number {
  return Math.exp(logMean + logSd * standardNormalQuantile(probability));
}
