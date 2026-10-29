import { inkFor } from "./theme";

/** O tooltip das séries, em ordem decrescente de valor — com várias séries no
 * mesmo ponto, a ordem da legenda obrigaria a procurar; a do valor põe quem
 * está por cima do cursor no topo. */
export function SeriesTip({
  active,
  payload,
  label,
  colors,
  format,
  dark,
  fillFor,
}: {
  active?: boolean;
  payload?: { dataKey?: string | number; value?: number }[];
  label?: string;
  colors: Record<string, string>;
  format: (value: number) => string;
  dark: boolean;
  /** Cor do marcador quando ela é da **faixa**, e não da série — o histograma
   * pintado por estado tem uma cor por barra, e o `dataKey` é o mesmo em
   * todas. */
  fillFor?: (label: string | undefined) => string | undefined;
}) {
  if (!active || !payload?.length) return null;
  const ink = inkFor(dark);
  const rows = payload
    .filter((row) => typeof row.value === "number")
    .sort((a, b) => (b.value as number) - (a.value as number));

  return (
    <div className="tooltip">
      <div className="tooltip-title">{label}</div>
      {rows.map((row) => (
        <div className="tooltip-row" key={String(row.dataKey)}>
          <span
            className="swatch"
            style={{ background: fillFor?.(label) ?? colors[String(row.dataKey)] }}
          />
          <span className="tooltip-label">{String(row.dataKey)}</span>
          <span className="tooltip-value" style={{ color: ink.secondary }}>
            {format(row.value as number)}
          </span>
        </div>
      ))}
    </div>
  );
}
