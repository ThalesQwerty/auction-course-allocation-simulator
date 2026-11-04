/** A densidade da nota, sobre a escala inteira de 0 a 10.
 *
 * A nota é **discreta**: múltiplos de um décimo, que é a resolução em que o
 * motor a entrega. Então o que a curva anda é a massa de cada décimo dividida
 * pelo passo — uma densidade de verdade, que integra 1, e em que todo ponto do
 * desenho é uma nota que a simulação pode de fato produzir.
 *
 * As pontas **não** fecham no eixo, e é o ponto da distribuição: a nota 0 e a
 * nota 10 carregam toda a massa que o latente põe fora da escala, porque a
 * escala para aí. São os dois átomos da censura, e aparecem como os dois picos
 * das extremidades — tão altos quanto a chance que o perfil declarou.
 *
 * Em t > 1 o que sai é a nota que a **população inteira** tiraria naquela
 * tentativa, e não a dos recursantes: quem recursa é quem foi mal, então a
 * amostra real de uma segunda tentativa é a cauda de baixo. Isto responde
 * "quanto a tentativa vale", não "como ficou a turma de repetentes".
 */
import { splitNormalCdf } from "./splitNormalCdf";

const POINTS = 101;
const TOP = 10;
const STEP = TOP / (POINTS - 1);

export function gradeDensity(
  mode: number,
  leftSd: number,
  rightSd: number
): { xs: number[]; ys: number[] } {
  const xs: number[] = [];
  const ys: number[] = [];
  for (let i = 0; i < POINTS; i++) {
    const grade = i * STEP;
    // O décimo vai de meio passo abaixo a meio passo acima; nas pontas ele se
    // estende ao infinito, que é a censura.
    const low = i === 0 ? -Infinity : grade - STEP / 2;
    const high = i === POINTS - 1 ? Infinity : grade + STEP / 2;
    const mass =
      (high === Infinity ? 1 : splitNormalCdf(high, mode, leftSd, rightSd)) -
      (low === -Infinity ? 0 : splitNormalCdf(low, mode, leftSd, rightSd));
    xs.push(grade);
    ys.push(Math.max(0, mass) / STEP);
  }
  return { xs, ys };
}
