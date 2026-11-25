/** O que a repetição faz com a chance de aprovar */
export function attemptApproval(
  approvalRate: number,
  repetitionGain: number,
  previousAttempts: number
): number {
  const experience = 1 + Math.max(0, repetitionGain) * Math.max(0, previousAttempts);
  return Math.pow(approvalRate, 1 / experience);
}
