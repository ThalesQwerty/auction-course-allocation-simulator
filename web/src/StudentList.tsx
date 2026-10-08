import { useMemo, useState } from "react";
import { formatRatio } from "./charts";
import { cohortLabel } from "./types";
import type { StudentSummary } from "./types";

type SortKey = "name" | "cohort" | "cohort-name";

const SORTS: { value: SortKey; label: string }[] = [
  { value: "cohort-name", label: "geração, depois nome" },
  { value: "name", label: "nome" },
  { value: "cohort", label: "geração" },
];

/** Vazio = sem filtro. Combina com a busca por nome, que é o que sobrou para
 * chegar a um aluno depois que os perfis saíram do modelo. */
const ALL = "";

/** Normaliza para busca: sem acento e sem caixa, para "jose" achar "José". */
const fold = (text: string) =>
  text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function StudentList({
  students,
  cohorts,
  colors,
  selectedId,
  onSelect,
}: {
  students: StudentSummary[];
  /** Os períodos de ingresso presentes na execução, em ordem. */
  cohorts: number[];
  colors: Record<string, string>;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [search, setSearch] = useState("");
  const [cohort, setCohort] = useState(ALL);
  const [sort, setSort] = useState<SortKey>("cohort-name");

  const visible = useMemo(() => {
    const needle = fold(search.trim());
    const wanted = cohort === ALL ? null : Number(cohort);
    const byName = (a: StudentSummary, b: StudentSummary) => a.name.localeCompare(b.name, "pt-BR");
    const byCohort = (a: StudentSummary, b: StudentSummary) => a.entry_period - b.entry_period;

    return students
      .filter(
        (s) =>
          (wanted === null || s.entry_period === wanted) &&
          (!needle || fold(s.name).includes(needle))
      )
      .sort(
        sort === "name" ? byName : sort === "cohort" ? byCohort : (a, b) => byCohort(a, b) || byName(a, b)
      );
  }, [students, search, cohort, sort]);

  return (
    <aside className="rail" aria-label="Alunos">
      <div className="rail-head">
        <h2>Alunos</h2>
        <input
          type="search"
          placeholder="pesquisar por nome"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="rail-filters">
          <select
            value={cohort}
            onChange={(e) => setCohort(e.target.value)}
            aria-label="Filtrar por geração"
          >
            <option value="">todas as gerações</option>
            {cohorts.map((entry) => (
              <option key={entry} value={entry}>
                {cohortLabel(entry)}
              </option>
            ))}
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Ordenar">
            {SORTS.map((option) => (
              <option key={option.value} value={option.value}>
                {`ordenar: ${option.label}`}
              </option>
            ))}
          </select>
        </div>
        <p className="rail-count">
          {visible.length === students.length
            ? `${students.length} alunos`
            : `${visible.length} de ${students.length} alunos`}
          {selectedId && (
            <button className="link" onClick={() => onSelect(null)}>
              voltar ao agregado
            </button>
          )}
        </p>
      </div>

      <ul className="rail-list">
        {visible.map((student) => (
          <li key={student.id}>
            <button
              className={`rail-item ${student.id === selectedId ? "current" : ""}`}
              onClick={() => onSelect(student.id)}
            >
              <span className="rail-item-name">
                <span
                  className="swatch"
                  style={{ background: colors[cohortLabel(student.entry_period)] }}
                />
                {student.name}
                {student.graduated_at ? <span className="badge">formado</span> : null}
              </span>
              <span className="rail-item-stats">
                CR {formatRatio(student.grade_average)} · ψ {formatRatio(student.mean_satisfaction)} ·{" "}
                {student.approved_hours}/{student.hours_to_graduate} h
              </span>
            </button>
          </li>
        ))}
        {visible.length === 0 && <li className="rail-empty">Nenhum aluno com esse nome.</li>}
      </ul>
    </aside>
  );
}
