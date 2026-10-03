import type { AffinityProfileInput, AptitudeProfileInput } from "./types";

/** Reparte `total` unidades inteiras entre as fatias de `weights`, pelo método
 * do maior resto: cada uma leva a parte inteira da sua fatia e as sobras vão às
 * maiores frações. Espelha `leilao.config.apportion`.
 *
 * A conta é duplicada aqui porque a tela de configuração mostra a composição de
 * uma geração enquanto o usuário edita as fatias — antes de existir execução
 * alguma para perguntar ao motor. */
export function apportion(total: number, weights: number[]): number[] {
  if (total <= 0 || weights.length === 0) return weights.map(() => 0);
  const scale = weights.reduce((sum, weight) => sum + weight, 0);
  if (scale <= 0) return weights.map(() => 0);
  const exact = weights.map((weight) => (total * weight) / scale);
  const counts = exact.map(Math.floor);
  const rest = total - counts.reduce((sum, count) => sum + count, 0);
  const order = [...counts.keys()].sort(
    (a, b) => exact[b] - counts[b] - (exact[a] - counts[a]) || a - b
  );
  for (const index of order.slice(0, rest)) counts[index] += 1;
  return counts;
}

export interface Combination {
  aptitude: string;
  affinity: string;
  /** Fatia da combinação: o produto das duas fatias, já em %. */
  share: number;
  /** Quantos alunos de cada geração caem nela, depois do arredondamento. */
  count: number;
}

/** A composição de **uma** geração: toda combinação (aptidão × afinidade), com
 * a fatia que lhe cabe e quantos alunos inteiros isso dá.
 *
 * Os dois eixos são independentes, então a fatia de uma combinação é o produto
 * das duas — e é sobre esse produto que a repartição inteira é feita, não sobre
 * cada eixo em separado. */
export function generationMix(
  size: number,
  aptitudes: AptitudeProfileInput[],
  affinities: AffinityProfileInput[]
): Combination[] {
  const pairs = aptitudes.flatMap((aptitude) =>
    affinities.map((affinity) => ({ aptitude, affinity }))
  );
  const counts = apportion(
    size,
    pairs.map(({ aptitude, affinity }) => aptitude.share * affinity.share)
  );
  return pairs.map(({ aptitude, affinity }, i) => ({
    aptitude: aptitude.name,
    affinity: affinity.name,
    share: (aptitude.share * affinity.share) / 100,
    count: counts[i],
  }));
}
