import { useMemo, useState } from "react";
import { formatRatio } from "./charts";
import type { StudentSummary } from "./types";

type SortKey = "name" | "course" | "course-name";

const SORTS: { value: SortKey; label: string }[] = [
  { value: "course-name", label: "curso, depois nome" },
  { value: "name", label: "nome" },
  { value: "course", label: "curso" },
];

/** Normaliza para busca: sem acento e sem caixa, para "jose" achar "José". */
const fold = (text: string) =>
  text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function StudentList({
  students,
  courses,
  colors,
  selectedId,
  onSelect,
}: {
  students: StudentSummary[];
  courses: string[];
  colors: Record<string, string>;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [search, setSearch] = useState("");
  const [course, setCourse] = useState("");
  const [sort, setSort] = useState<SortKey>("course-name");

  const visible = useMemo(() => {
    const needle = fold(search.trim());
    const order = courses.reduce<Record<string, number>>((acc, name, i) => ({ ...acc, [name]: i }), {});
    const byName = (a: StudentSummary, b: StudentSummary) => a.name.localeCompare(b.name, "pt-BR");
    const byCourse = (a: StudentSummary, b: StudentSummary) => order[a.course] - order[b.course];

    return students
      .filter((s) => (!course || s.course === course) && (!needle || fold(s.name).includes(needle)))
      .sort(
        sort === "name" ? byName : sort === "course" ? byCourse : (a, b) => byCourse(a, b) || byName(a, b)
      );
  }, [students, courses, search, course, sort]);

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
          <select value={course} onChange={(e) => setCourse(e.target.value)} aria-label="Filtrar por curso">
            <option value="">todos os cursos</option>
            {courses.map((name) => (
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
                <span className="swatch" style={{ background: colors[student.course] }} />
                {student.name}
                {student.graduated_at ? (
                  <span className="badge">formado</span>
                ) : student.dismissed_at ? (
                  <span className="badge">jubilado</span>
                ) : null}
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
