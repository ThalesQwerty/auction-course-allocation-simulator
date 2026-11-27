import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type ColumnKind = "texto" | "numero" | "enum";

/** O descritor de uma coluna: o comparador e o filtro saem do `tipo` */
export interface Column<T> {
  chave: string;
  rotulo: string;
  tipo: ColumnKind;
   /** O valor que ordena e filtra; `null` vai para o fim nas duas direções */
  valor: (row: T) => string | number | null;
   /** O que a célula desenha; ausente, desenha o valor */
  escreve?: (row: T) => ReactNode;
   /** A ordem do enum, na qual o índice é o critério */
  ordem?: readonly string[];
  filtro?: boolean;
}

export interface SortState {
  chave: string;
  desc: boolean;
}

interface Filter {
  texto?: string;
  min?: string;
  max?: string;
}

const COLLATOR = new Intl.Collator("pt-BR");

/** Crescente em texto e enum, decrescente em número: é a leitura útil de cada um */
const firstDescending = (kind: ColumnKind) => kind === "numero";

const empty = (value: string | number | null) =>
  value === null || value === undefined || value === "";

function order<T>(
  column: Column<T>,
  left: string | number,
  right: string | number
): number {
  if (column.tipo === "numero") return Number(left) - Number(right);
  if (column.tipo === "enum") {
    const ordem = column.ordem ?? [];
    return ordem.indexOf(String(left)) - ordem.indexOf(String(right));
  }
  return COLLATOR.compare(String(left), String(right));
}

export function sortRows<T>(
  rows: T[],
  columns: Column<T>[],
  sort: SortState
): T[] {
  const column = columns.find((entry) => entry.chave === sort.chave);
  if (!column) return rows;
  const sign = sort.desc ? -1 : 1;
  return [...rows].sort((a, b) => {
    const left = column.valor(a);
    const right = column.valor(b);
    if (empty(left) || empty(right)) {
      if (empty(left) && empty(right)) return 0;
      return empty(left) ? 1 : -1;
    }
    return sign * order(column, left as string | number, right as string | number);
  });
}

const normalize = (value: string) =>
  value
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");

function keeps<T>(column: Column<T>, filter: Filter, row: T): boolean {
  const value = column.valor(row);
  if (column.tipo === "numero") {
    if (empty(value)) return !filter.min && !filter.max;
    const number = Number(value);
    const min = Number(filter.min);
    const max = Number(filter.max);
    if (filter.min && Number.isFinite(min) && number < min) return false;
    if (filter.max && Number.isFinite(max) && number > max) return false;
    return true;
  }
  if (!filter.texto) return true;
  if (column.tipo === "enum") return String(value) === filter.texto;
  return normalize(String(value ?? "")).includes(normalize(filter.texto));
}

export function DataTable<T>({
  rows,
  columns,
  chave,
  inicial,
  pagina,
  aoEscolher,
  escolhido,
  vazio = "Nada a mostrar.",
}: {
  rows: T[];
  columns: Column<T>[];
  chave: (row: T) => string;
  inicial: SortState;
   /** Linhas por página; ausente mostra tudo e não pagina */
  pagina?: number;
  aoEscolher?: (row: T) => void;
  escolhido?: string;
  vazio?: string;
}) {
  const [sort, setSort] = useState<SortState>(inicial);
  const [filters, setFilters] = useState<Record<string, Filter>>({});
  const [page, setPage] = useState(0);
  const filtered = columns.some((column) => column.filtro);

  const visible = useMemo(() => {
    const kept = rows.filter((row) =>
      columns.every((column) =>
        !column.filtro || !filters[column.chave]
          ? true
          : keeps(column, filters[column.chave], row)
      )
    );
    return sortRows(kept, columns, sort);
  }, [rows, columns, filters, sort]);

  const pages = pagina ? Math.max(1, Math.ceil(visible.length / pagina)) : 1;
  useEffect(() => {
    if (page >= pages) setPage(0);
  }, [page, pages]);
  const start = pagina ? Math.min(page, pages - 1) * pagina : 0;
  const slice = pagina ? visible.slice(start, start + pagina) : visible;

  const toggle = (column: Column<T>) =>
    setSort((current) =>
      current.chave === column.chave
        ? { chave: column.chave, desc: !current.desc }
        : { chave: column.chave, desc: firstDescending(column.tipo) }
    );

  const change = (column: Column<T>, part: keyof Filter, value: string) => {
    setPage(0);
    setFilters((current) => ({
      ...current,
      [column.chave]: { ...current[column.chave], [part]: value },
    }));
  };

  return (
    <div className="data-table">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.chave}>
                <button
                  type="button"
                  className={`sort${sort.chave === column.chave ? " on" : ""}`}
                  onClick={() => toggle(column)}
                >
                  {column.rotulo}
                  <span className="sort-mark">
                    {sort.chave === column.chave ? (sort.desc ? "▾" : "▴") : ""}
                  </span>
                </button>
              </th>
            ))}
          </tr>
          {filtered && (
            <tr className="filter-row">
              {columns.map((column) => (
                <th key={column.chave}>
                  {!column.filtro ? null : column.tipo === "numero" ? (
                    <div className="filter-range">
                      <input
                        type="text"
                        inputMode="decimal"
                        aria-label={`${column.rotulo}: mínimo`}
                        value={filters[column.chave]?.min ?? ""}
                        onChange={(event) =>
                          change(column, "min", event.target.value)
                        }
                      />
                      <input
                        type="text"
                        inputMode="decimal"
                        aria-label={`${column.rotulo}: máximo`}
                        value={filters[column.chave]?.max ?? ""}
                        onChange={(event) =>
                          change(column, "max", event.target.value)
                        }
                      />
                    </div>
                  ) : column.tipo === "enum" ? (
                    <select
                      aria-label={column.rotulo}
                      value={filters[column.chave]?.texto ?? ""}
                      onChange={(event) =>
                        change(column, "texto", event.target.value)
                      }
                    >
                      <option value="">todos</option>
                      {(column.ordem ?? []).map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      aria-label={column.rotulo}
                      value={filters[column.chave]?.texto ?? ""}
                      onChange={(event) =>
                        change(column, "texto", event.target.value)
                      }
                    />
                  )}
                </th>
              ))}
            </tr>
          )}
        </thead>
        <tbody>
          {slice.map((row) => (
            <tr
              key={chave(row)}
              className={[
                aoEscolher ? "clickable" : "",
                escolhido === chave(row) ? "current" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={aoEscolher ? () => aoEscolher(row) : undefined}
            >
              {columns.map((column) => (
                <td key={column.chave}>
                  {column.escreve
                    ? column.escreve(row)
                    : (column.valor(row) ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {slice.length === 0 && <p className="empty-state">{vazio}</p>}

      {pagina && visible.length > pagina && (
        <div className="table-foot">
          <button
            type="button"
            className="ghost"
            disabled={start === 0}
            onClick={() => setPage((current) => Math.max(0, current - 1))}
          >
            Anteriores
          </button>
          <span>
            {start + 1}–{start + slice.length} de {visible.length}
          </span>
          <button
            type="button"
            className="ghost"
            disabled={start + slice.length >= visible.length}
            onClick={() => setPage((current) => Math.min(pages - 1, current + 1))}
          >
            Seguintes
          </button>
        </div>
      )}
    </div>
  );
}
