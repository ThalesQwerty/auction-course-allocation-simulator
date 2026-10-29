/** Quantil por interpolação linear entre as ordens estatísticas.
 *
 *     posição = p · (n − 1)
 *     q = x_⌊posição⌋ + frac(posição) · (x_⌈posição⌉ − x_⌊posição⌋)
 *
 * É o **método 7**, padrão do R e do numpy. Com N pequeno — e a comparação
 * roda com 20 seeds — a escolha do método desloca os quartis visivelmente,
 * então convém que seja a mesma que qualquer conferência externa usaria.
 *
 * Espera a amostra **já ordenada**.
 */
export function quantile(sorted: number[], p: number): number {
  if (sorted.length === 1) return sorted[0];
  const position = p * (sorted.length - 1);
  const floor = Math.floor(position);
  const rest = position - floor;
  return rest === 0
    ? sorted[floor]
    : sorted[floor] + rest * (sorted[floor + 1] - sorted[floor]);
}
