/** A faixa de valor a que um aluno pertence, e o nome dela — espelha `equations/value_band.py` */

export const WHOLE = "Geral";

/** Os cortes em ordem crescente, que é a ordem dos índices de faixa */
export function orderedCuts(cuts: number[]): number[] {
  return [...new Set(cuts)].sort((a, b) => a - b);
}

/** O índice da faixa, de 0 (a mais baixa) a `cuts.length`. O corte pertence à faixa que abre */
export function valueBand(value: number, cuts: number[]): number {
  const ordered = orderedCuts(cuts);
  let band = 0;
  while (band < ordered.length && value >= ordered[band]) band += 1;
  return band;
}

/** O rótulo da faixa — o intervalo que ela cobre, nas unidades da grandeza */
export function valueBandName(
  band: number,
  cuts: number[],
  low: number,
  high: number,
  decimals = 0
): string {
  const ordered = orderedCuts(cuts);
  if (!ordered.length) return WHOLE;
  const start = band === 0 ? low : ordered[band - 1];
  const end = band === ordered.length ? high : ordered[band];
  return `${asNumber(start, decimals)}–${asNumber(end, decimals)}`;
}

/** Os rótulos das faixas, da mais baixa para a mais alta */
export function valueBandNames(
  cuts: number[],
  low: number,
  high: number,
  decimals = 0
): string[] {
  const ordered = orderedCuts(cuts);
  return ordered.map((_, band) =>
    valueBandName(band, cuts, low, high, decimals)
  ).concat(valueBandName(ordered.length, cuts, low, high, decimals));
}

/** O número como a interface o escreve: vírgula decimal, sem zero à toa */
function asNumber(value: number, decimals: number): string {
  if (decimals <= 0) return String(Math.round(value));
  const text = value
    .toFixed(decimals)
    .replace(/0+$/, "")
    .replace(/\.$/, "");
  return (text || "0").replace(".", ",");
}
