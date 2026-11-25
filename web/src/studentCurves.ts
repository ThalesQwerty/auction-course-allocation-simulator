/** A curva de uma métrica sobre uma grandeza de vida inteira do aluno.
 *
 * Um ponto é uma **faixa de quantil** da população medida: a mediana e o
 * intervalo interquartil dos alunos que caem nela. As bordas saem dos quantis
 * dos dois braços **juntos**, de modo que ambos usem as mesmas e as linhas se
 * comparem ponto a ponto, e cada ponto é posicionado na mediana de X da faixa.
 *
 * A banda aqui é dispersão **entre alunos**, não entre seeds como nas séries
 * por período.
 */
import type { BandPoint } from "./charts";
import { boxStats } from "./equations";
import type { StudentPoint } from "./types";

/** Quantos alunos uma faixa precisa ter para render um ponto */
const MINIMUM = 2;

export interface CurveSeries {
  key: string;
  points: StudentPoint[];
}

/** As bordas das faixas, dos quantis da população inteira, estritamente crescentes */
function quantileEdges(values: number[], bins: number): number[] {
  const sorted = [...values].sort((a, b) => a - b);
  const edges: number[] = [];
  for (let k = 1; k < bins; k += 1) {
    const edge = sorted[Math.floor((k * sorted.length) / bins)];
    if (edge !== undefined && (!edges.length || edge > edges[edges.length - 1])) {
      edges.push(edge);
    }
  }
  return edges;
}

/** Em que faixa o valor cai, de 0 a `edges.length` */
function binOf(value: number, edges: number[]): number {
  let bin = 0;
  while (bin < edges.length && value >= edges[bin]) bin += 1;
  return bin;
}

const median = (sorted: number[]): number =>
  sorted.length % 2
    ? sorted[(sorted.length - 1) / 2]
    : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;

/** Uma curva por braço, todas sobre as mesmas faixas */
export function studentCurves(
  series: CurveSeries[],
  xOf: (point: StudentPoint) => number,
  yOf: (point: StudentPoint) => number | null,
  bins: number
): Record<string, BandPoint[]> {
  const taken = series.map((entry) => ({
    key: entry.key,
    rows: entry.points.flatMap((point) => {
      const y = yOf(point);
      const x = xOf(point);
      return y === null || y === undefined || !Number.isFinite(x)
        ? []
        : [{ x, y }];
    }),
  }));

  const pooled = taken.flatMap((entry) => entry.rows.map((row) => row.x));
  const povoados = taken.filter((entry) => entry.rows.length);
  if (pooled.length < MINIMUM || !povoados.length) {
    return Object.fromEntries(taken.map((entry) => [entry.key, []]));
  }
   // Mais faixas do que a coorte sustenta deixariam cada ponto sobre um aluno
   // ou dois, e aí cada braço perderia faixas diferentes e as linhas
   // desalinhariam. O pedido é teto, não promessa.
  const cabem = Math.floor(pooled.length / (MINIMUM * povoados.length));
  const edges = quantileEdges(pooled, Math.max(1, Math.min(bins, cabem)));

  /** A posição X de cada faixa: a mediana dos dois braços juntos, para as linhas coincidirem */
  const positions = new Map<number, number>();
  const byBin = new Map<number, number[]>();
  pooled.forEach((x) => {
    const bin = binOf(x, edges);
    const values = byBin.get(bin);
    if (values) values.push(x);
    else byBin.set(bin, [x]);
  });
  byBin.forEach((values, bin) =>
    positions.set(bin, median([...values].sort((a, b) => a - b)))
  );

  const grouped = new Map<string, Map<number, number[]>>();
  taken.forEach((entry) => {
    const bins_ = new Map<number, number[]>();
    entry.rows.forEach((row) => {
      const bin = binOf(row.x, edges);
      const values = bins_.get(bin);
      if (values) values.push(row.y);
      else bins_.set(bin, [row.y]);
    });
    grouped.set(entry.key, bins_);
  });

   // A faixa só rende ponto se **todo** braço povoado a sustenta: assim os dois
   // desenham os mesmos X e o tooltip compara os dois no mesmo ponto.
  const kept = [...positions.keys()]
    .filter((bin) =>
      povoados.every(
        (entry) => (grouped.get(entry.key)?.get(bin)?.length ?? 0) >= MINIMUM
      )
    )
    .sort((a, b) => a - b);

  return Object.fromEntries(
    taken.map((entry) => {
      const bins_ = grouped.get(entry.key);
      const points: BandPoint[] = [];
      kept.forEach((bin) => {
        const values = bins_?.get(bin);
        const stats = values ? boxStats(values) : null;
        const x = positions.get(bin);
        if (!stats || !values || x === undefined) return;
        points.push({
          x,
          q1: stats.q1,
          median: stats.median,
          q3: stats.q3,
          n: values.length,
        });
      });
      return [entry.key, points];
    })
  );
}
