/** A densidade da log-normal num grid */
const POINTS = 161;

export function lognormalDensity(
  logMean: number,
  logSd: number,
  top: number
): { xs: number[]; ys: number[] } {
  const xs: number[] = [];
  const ys: number[] = [];
  const step = top / (POINTS - 1);
  for (let i = 0; i < POINTS; i++) {
    const hours = i * step;
    xs.push(hours);
    if (hours <= 0) {
      ys.push(0);
      continue;
    }
    const z = (Math.log(hours) - logMean) / logSd;
    ys.push(
      Math.exp(-0.5 * z * z) / (hours * logSd * Math.sqrt(2 * Math.PI))
    );
  }
  return { xs, ys };
}
