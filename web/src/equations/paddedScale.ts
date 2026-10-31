/** A régua vertical de um gráfico de comparação.
 *
 * Duas regras, e a primeira manda:
 *
 * 1. **Contradomínio definido é a régua inteira.** ψ̄ vive em [0, 1] e λ em
 *    [−1, 1], e é nesse intervalo que eles se desenham — sempre, independente
 *    de onde a amostra caiu. Fechar a régua em torno dos dados faria um vão de
 *    0,02 ocupar meia altura do cartão e parecer o que não é, e faria cada
 *    métrica ter uma escala diferente da vizinha na mesma grade. A precisão que
 *    o olho perde assim está nas tabelas, que é onde ela se lê sem ilusão.
 *
 * 2. **Sem contradomínio, folga em torno dos dados.** É o caso do tempo de
 *    formatura, que não tem teto, e o da saturação, limitada só por baixo: ali
 *    a régua se ajusta à amostra, arredondada por `niceScale` e aparada no lado
 *    que tem limite.
 *
 * `padding` é a folga como fração da dispersão. Uma caixa precisa de mais ar
 * que uma linha — os bigodes dela já alcançam os extremos, enquanto a faixa de
 * uma série é só a metade central.
 */
import { niceScale } from "./niceScale";

/** Folga mínima para uma amostra sem dispersão: sem ela a marca fica colada no
 * eixo. */
const FLAT = 0.01;

export interface Scale {
  from: number;
  to: number;
  ticks: number[];
}

export function paddedScale(
  values: number[],
  {
    bounds,
    zeroLine = false,
    padding,
  }: { bounds?: [number, number]; zeroLine?: boolean; padding: number }
): Scale {
  // Regra 1: os dois limites finitos *são* a régua, mesmo sem dado algum —
  // um cartão vazio com a régua certa diz mais que um cartão sem régua.
  if (bounds && Number.isFinite(bounds[0]) && Number.isFinite(bounds[1])) {
    const [from, to] = bounds;
    return {
      from,
      to,
      ticks: niceScale(from, to).ticks.filter(
        (tick) => tick >= from - 1e-9 && tick <= to + 1e-9
      ),
    };
  }

  if (!values.length) return { from: 0, to: 1, ticks: [0, 1] };

  let low = Math.min(...values);
  let high = Math.max(...values);
  if (zeroLine) {
    low = Math.min(low, 0);
    high = Math.max(high, 0);
  }
  const pad = (high - low) * padding || Math.max(Math.abs(high) * 0.05, FLAT);
  const nice = niceScale(low - pad, high + pad);
  // Regra 2 com um limite só: a saturação não passa de zero por baixo, mas não
  // tem teto por cima.
  return bounds
    ? { ...nice, from: Math.max(nice.from, bounds[0]), to: Math.min(nice.to, bounds[1]) }
    : nice;
}
