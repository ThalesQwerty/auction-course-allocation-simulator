/** Domínio e marcas arredondados a passos legíveis */
const STEPS = [1, 2, 2.5, 5, 10];
const FLAT_PADDING = 0.05;

export function niceScale(low: number, high: number, count = 4) {
  if (!(high > low)) {
    const pad = Math.abs(high) * FLAT_PADDING || FLAT_PADDING;
    low = high - pad;
    high = high + pad;
  }
  const rough = (high - low) / count;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const normalized = rough / magnitude;
  const step = (STEPS.find((candidate) => normalized <= candidate) ?? 10) * magnitude;

  const from = Math.floor(low / step) * step;
  const to = Math.ceil(high / step) * step;
  const ticks: number[] = [];
  for (let i = 0; from + i * step <= to + step / 2; i++) ticks.push(from + i * step);
  return { from, to: ticks[ticks.length - 1], ticks };
}
