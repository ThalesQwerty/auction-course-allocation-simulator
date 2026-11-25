/** Quantil por interpolação linear entre as ordens estatísticas */
export function quantile(sorted: number[], p: number): number {
  if (sorted.length === 1) return sorted[0];
  const position = p * (sorted.length - 1);
  const floor = Math.floor(position);
  const rest = position - floor;
  return rest === 0
    ? sorted[floor]
    : sorted[floor] + rest * (sorted[floor + 1] - sorted[floor]);
}
