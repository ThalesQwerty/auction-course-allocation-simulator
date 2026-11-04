import { SeriesChart } from "./charts";
import type { SeriesGroup } from "./charts";
import { GENES } from "./types";
import type { EvolveResponse } from "./types";

/** A trajetória de uma rodada do algoritmo genético.
 *
 * Uma série por gene, e dentro dela **uma amostra por coorte**: as linhagens
 * evoluem independentes, então o que a faixa mostra é o espalhamento entre
 * elas. Convergirem para a mesma região é evidência forte; divergirem diz que
 * a paisagem é plana ou tem vários picos — com a ressalva de que elas não
 * enfrentam o mesmo ambiente, porque a primeira coorte entra numa
 * universidade vazia e a última numa cheia.
 *
 * O que **não** se desenha aqui é a aptidão. Ela é medida relativa à média da
 * própria coorte, então a média relativa é ~0 por construção: um gráfico dela
 * seria uma linha reta em zero por motivo aritmético, não por resultado.
 */
export function Evolution({
  result,
  onReuse,
}: {
  result: EvolveResponse;
  onReuse: () => void;
}) {
  const cohorts = result.generations[0]?.cohorts.map((c) => c.entry_period) ?? [];
  const palette = Object.fromEntries(
    GENES.map((gene, i) => [gene.label, `var(--series-${i % 4})`])
  );

  const seriesFor = (index: number): SeriesGroup[] => [
    {
      label: GENES[index].label,
      samples: cohorts.map((entry) =>
        result.generations.map((generation) => ({
          x: generation.generation,
          y:
            generation.cohorts.find((c) => c.entry_period === entry)?.mean[index] ??
            0,
        }))
      ),
    },
  ];

  const drift: SeriesGroup[] = [
    {
      label: "deriva",
      samples: [
        result.generations
          .filter((generation) => generation.drift !== null)
          .map((generation) => ({
            x: generation.generation,
            y: generation.drift as number,
          })),
      ],
    },
  ];

  const last = result.generations[result.generations.length - 1];

  return (
    <div className="rail-layout">
      <div className="rail-layout-main">
        <h1>{result.neutral ? "Controle negativo" : "Evolução"}</h1>

        <div className="panel">
          <h2>
            {result.generations.length} gerações · parou por {result.stopped_by}
          </h2>
          {result.neutral && (
            <p className="note">
              O genoma foi selecionado e mutado, mas não chegou à simulação: o
              que a população andou aqui é deriva. É esta trajetória que calibra
              o ε das rodadas reais.
            </p>
          )}
          <table className="data-table">
            <thead>
              <tr>
                <th>Coorte</th>
                {GENES.map((gene) => (
                  <th key={gene.key}>{gene.label}</th>
                ))}
                <th>Aptidão média</th>
              </tr>
            </thead>
            <tbody>
              {last?.cohorts.map((cohort) => (
                <tr key={cohort.entry_period}>
                  <td>{cohort.entry_period}</td>
                  {cohort.mean.map((value, i) => (
                    <td key={GENES[i].key}>{value.toFixed(3)}</td>
                  ))}
                  <td>{cohort.mean_fitness.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {GENES.map((gene, index) => (
          <SeriesChart
            key={gene.key}
            title={`${gene.label} — ${gene.name}`}
            groups={seriesFor(index)}
            colors={palette}
            format={(value) => value.toFixed(2)}
            zeroLine
            runs={cohorts.length}
            xLabel={(x) => `g${x}`}
          />
        ))}

        <SeriesChart
          title="Deriva do genoma médio"
          groups={drift}
          colors={{ deriva: "var(--series-0)" }}
          format={(value) => value.toFixed(3)}
          runs={1}
          xLabel={(x) => `g${x}`}
        />

        <div className="actions">
          <button className="primary" onClick={onReuse}>
            Reabrir esta configuração
          </button>
        </div>
      </div>
    </div>
  );
}
