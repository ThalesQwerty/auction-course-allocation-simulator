/** O vão entre os extremos de uma amostra: amplitude = max − min Na comparação ela lê um **eixo de perfil**: a distância entre o grupo que mais colheu e o que menos colheu num ponto da régua, que é o quanto aquele eixo separou as pessoas ali */
export const amplitude = (values: number[]): number | null =>
  values.length < 2 ? null : Math.max(...values) - Math.min(...values);
