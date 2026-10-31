/** O expoente da fórmula da nota.
 *
 *     E = dificuldade / ( u_rel^g_u · esforço )
 *     esforço = 1 + g_t · (tentativa − 1)
 *
 * O denominador de `equations.grade_for_attempt`, isolado porque é o que a
 * prévia precisa: com ele, a densidade da nota sai em forma fechada e a
 * aprovação sai da quadratura.
 *
 * Os dois ganhos dividem este lugar, e por isso se leem juntos: com os dois em
 * 1 o expoente é a dificuldade dividida pela tentativa, de modo que
 * **dificuldade 2 na segunda tentativa equivale a dificuldade 1 na primeira**.
 *
 * Os pisos são da prévia, não do modelo: aqui eles evitam um gráfico
 * degenerado enquanto se digita; no motor é a validação do cenário que
 * recusa o valor.
 */
const MIN_DIFFICULTY = 0.1;
const MIN_ATTEMPTS = 1e-9;

export function gradeExponent({
  difficulty,
  attempt,
  relativeUtility,
  utilityGain,
  retakeGain,
}: {
  difficulty: number;
  attempt: number;
  relativeUtility: number;
  utilityGain: number;
  retakeGain: number;
}): number {
  // Campo vazio vira 0, e expoente 0 daria 10 para todo mundo.
  const d = difficulty > 0 ? difficulty : MIN_DIFFICULTY;
  // Com ganho 0 o fator é 1 e a utilidade relativa some da conta, que é o
  // controle a reportar ao lado de qualquer resultado em conclusões.
  const raised = relativeUtility > 0 ? Math.pow(relativeUtility, utilityGain) : 1;
  const utility = raised > 0 ? raised : 1;
  const attempts = Math.max(
    MIN_ATTEMPTS,
    1 + retakeGain * (Math.max(1, Math.floor(attempt)) - 1)
  );
  return d / (utility * attempts);
}
