/** A fração da população que alcança a nota mínima.
 *
 *     P(n ≥ n_min) = P(latente ≥ n_min − 0,05)
 *
 * O limiar é meio décimo abaixo de `n_min` porque a nota é arredondada: quem
 * tira 4,96 recebe 5,0 e aprova. Sai direto da acumulada — a normal dividida
 * tem forma fechada, e não precisa da quadratura que a Beta pedia.
 *
 * A taxa de aprovação **não** é parâmetro do perfil, de propósito: `n_min` é
 * regra de cenário, não propriedade do aluno. Ela é lida aqui, como resultado.
 */
import { splitNormalCdf } from "./splitNormalCdf";

export function approvalShare(
  mode: number,
  leftSd: number,
  rightSd: number,
  minGrade: number
): number {
  if (minGrade <= 0) return 1;
  return 1 - splitNormalCdf(minGrade - 0.05, mode, leftSd, rightSd);
}
