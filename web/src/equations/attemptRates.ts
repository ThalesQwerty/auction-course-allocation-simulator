/** O que a dificuldade e a tentativa fazem com as duas chances da nota.
 *
 *     chance de 0  = chance_base_de_0 ^ (tentativa / dificuldade)
 *     chance de 10 = chance_base_de_10 ^ (dificuldade / tentativa)
 *
 * O espelho de `equations.attempt_rates`. Os expoentes são recíprocos, e daí
 * sai a lei de potência da prática: **dificuldade 2 na segunda tentativa
 * reproduz dificuldade 1 na primeira**.
 */
export function attemptRates(
  zeroRate: number,
  maxRate: number,
  difficulty: number,
  attempt: number
): [zeroRate: number, maxRate: number] {
  return [
    Math.pow(zeroRate, attempt / difficulty),
    Math.pow(maxRate, difficulty / attempt),
  ];
}
