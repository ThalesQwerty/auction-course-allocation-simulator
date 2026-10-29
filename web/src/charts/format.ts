/** Os dois formatos de número dos gráficos.
 *
 * `formatRatio` tem duas casas **fixas**: numa coluna de valores entre 0 e 1,
 * casas variáveis desalinham a vírgula e a comparação de relance se perde.
 * `formatCount` tem no máximo uma, porque contagens por aluno já se leem
 * inteiras na maior parte das vezes.
 */
export const formatRatio = (value: number) =>
  value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const formatCount = (value: number) =>
  value.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
