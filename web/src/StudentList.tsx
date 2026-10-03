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

/** Vazio = sem filtro naquele eixo. Os três se combinam, então dá para isolar
 * uma única célula da grade de perfis dentro de uma geração — é o recorte que
 * a tela individual depois abre aluno a aluno. */
const ALL = "";

/** Normaliza para busca: sem acento e sem caixa, para "jose" achar "José". */
const fold = (text: string) =>
  text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function StudentList({
  students,
  cohorts,
  aptitudes,
  affinities,
  colors,
  selectedId,
  onSelect,
}: {
  students: StudentSummary[];
  /** Os períodos de ingresso presentes na execução, em ordem. */
  cohorts: number[];
  /** Os perfis do cenário, na ordem em que ele os declara. */
  aptitudes: string[];
  affinities: string[];
  colors: Record<string, string>;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [search, setSearch] = useState("");
  const [cohort, setCohort] = useState(ALL);
  const [aptitude, setAptitude] = useState(ALL);
  const [affinity, setAffinity] = useState(ALL);
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
          (aptitude === ALL || s.aptitude === aptitude) &&
          (affinity === ALL || s.affinity === affinity) &&
          (!needle || fold(s.name).includes(needle))
      )
      .sort(
        sort === "name" ? byName : sort === "cohort" ? byCohort : (a, b) => byCohort(a, b) || byName(a, b)
      );
  }, [students, search, cohort, aptitude, affinity, sort]);

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
          <select
            value={aptitude}
            onChange={(e) => setAptitude(e.target.value)}
            aria-label="Filtrar por perfil de aptidão"
          >
            <option value={ALL}>toda aptidão</option>
            {aptitudes.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <select
            value={affinity}
            onChange={(e) => setAffinity(e.target.value)}
            aria-label="Filtrar por perfil de afinidade"
          >
            <option value={ALL}>toda afinidade</option>
            {affinities.map((name) => (
              <option key={name} value={name}>
                {name}
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
