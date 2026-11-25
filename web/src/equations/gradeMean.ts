/** A média da normal das notas, dada a taxa de aprovação */
import { standardNormalQuantile } from "./_standardNormal";

export function gradeMean(
  minGrade: number,
  gradeSd: number,
  approvalRate: number
): number | null {
  if (!(gradeSd > 0)) return null;
  if (!(approvalRate > 0 && approvalRate < 1)) return null;
  return minGrade + gradeSd * standardNormalQuantile(approvalRate);
}
