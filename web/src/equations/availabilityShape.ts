/** Os parâmetros da normal da disponibilidade, a partir do desvio e da chance */
import { standardNormalQuantile } from "./_standardNormal";

export function availabilityShape(
  hoursSd: number,
  fullLoadRate: number,
  maxHours: number
): [mean: number, sd: number] | null {
  if (!(hoursSd > 0) || !(maxHours > 0)) return null;
  if (!(fullLoadRate > 0 && fullLoadRate < 1)) return null;
  return [maxHours + hoursSd * standardNormalQuantile(fullLoadRate), hoursSd];
}
