/** De onde sai o ε do critério de parada.
 *
 * O limiar não é um número que se escolha: é a deriva que o **controle
 * negativo** mediu sob exatamente as mesmas condições. Digitá-lo à mão seria
 * chutar uma grandeza sem escala intuitiva — deriva do genoma médio
 * normalizada pelo espalhamento de cada gene na 1ª geração —, então o
 * formulário não oferece campo. Oferece o número que um nulo já produziu.
 *
 * **Reaproveitar em vez de recalibrar.** Rodar o nulo dentro do `/evolve`
 * dobraria o custo de toda evolução; aqui o controle roda uma vez e o ε serve
 * a quantos experimentos vierem depois, enquanto nada que mude a escala da
 * deriva mudar.
 */
import type { EvolutionRun, HistoryEntry } from "./history";
import type { EvolveRequest, EvolveResponse } from "./types";

/** O ε que um controle negativo mediu, e quando. */
export interface Calibration {
  epsilon: number;
  at: string;
}

/** O que **não** precisa bater entre o nulo e o experimento.
 *
 * A seed dá outra realização da mesma deriva, não outra deriva. O piso e o
 * teto de gerações só dizem quando a rodada termina. O próprio ε é o que está
 * sendo transportado, e `neutral` é justamente o que diferencia os dois lados.
 *
 * Todo o resto entra: o cenário inteiro, porque é ele que produz a aptidão, e
 * os parâmetros do AG que governam quanto a população anda por geração —
 * passo, observações, torneio, elites, níveis e a janela sobre a qual a
 * deriva é medida. */
const VOLATILE = new Set([
  "seed",
  "epsilon",
  "neutral",
  "min_generations",
  "max_generations",
]);

/** Forma canônica: chaves ordenadas em toda profundidade e nulos descartados.
 *
 * A ordem importa porque um pedido montado aqui e o mesmo pedido lido de um
 * arquivo gravado pela API não têm as chaves na mesma sequência. Os nulos
 * importam pelo mesmo motivo: o Pydantic escreve os campos opcionais que o
 * formulário simplesmente não monta. */
const canonical = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([, inner]) => inner !== null && inner !== undefined)
        .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
        .map(([name, inner]) => [name, canonical(inner)])
    );
  }
  return value;
};

export const calibrationKey = (request: EvolveRequest): string =>
  JSON.stringify(
    canonical(
      Object.fromEntries(
        Object.entries(request).filter(([name]) => !VOLATILE.has(name))
      )
    )
  );

/** A deriva da última janela — o desvio do genoma médio nas `window` gerações
 * finais, que é exatamente o ε. Nula enquanto a janela não fecha. */
const finalDrift = (result: EvolveResponse): number | null =>
  result.generations.length
    ? result.generations[result.generations.length - 1].drift
    : null;

/** O ε do controle negativo mais recente que rodou nestas condições, ou nulo
 * se não houver nenhum.
 *
 * Um nulo interrompido fica de fora: ele parou na janela mais parada que
 * apareceu, e o ε sairia enviesado para baixo. O motor já não deixa isso
 * acontecer, mas execuções gravadas antes disso continuam no histórico. */
export function findCalibration(
  history: HistoryEntry[],
  request: EvolveRequest
): Calibration | null {
  const wanted = calibrationKey(request);
  for (const entry of history) {
    if (entry.kind !== "evolution") continue;
    const run = entry as EvolutionRun;
    if (!run.result.neutral || run.result.stopped_by === "convergiu") continue;
    if (calibrationKey(run.config) !== wanted) continue;
    const drift = finalDrift(run.result);
    if (drift !== null) return { epsilon: drift, at: run.at };
  }
  return null;
}
