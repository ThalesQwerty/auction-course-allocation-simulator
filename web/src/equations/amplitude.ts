/** O vão entre os extremos de uma amostra:
 *
 *     amplitude = max − min
 *
 * Na comparação ela lê um **eixo de perfil**: a distância entre o grupo que
 * mais colheu e o que menos colheu num ponto da régua, que é o quanto aquele
 * eixo separou as pessoas ali.
 *
 * Com menos de dois valores o resultado é `null`, e não zero: um eixo com um
 * grupo só, ou um ponto em que só um grupo foi medido, não diz que os grupos
 * empataram — diz que não houve comparação.
 */
export const amplitude = (values: number[]): number | null =>
  values.length < 2 ? null : Math.max(...values) - Math.min(...values);
