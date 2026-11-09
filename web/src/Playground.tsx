import { useState } from "react";
import { playground } from "./api";
import type { DisciplineInput, Mechanism, PlaygroundResponse, Scenario } from "./types";

interface PlaygroundStudent {
  id: string;
  label: string;
  credits: number;
  cr: number;
  maxHours: number;
  /** δ em horas, já realizada: aqui não há perfil de onde sorteá-la. */
  availability: number;
  selectivity: number;
  concentration: number;
  /** Utilidade por **turma**: é a turma que se aloca, como na simulação. */
  rows: Record<string, number>;
}

export interface PlaygroundDraft {
  mechanism: Mechanism;
  rounds: number;
  /** Vagas de cada turma. */
  seats: number;
  seed: number;
  modeGrade: number;
  zeroRate: number;
  maxRate: number;
  selected: number;
  students: PlaygroundStudent[];
}

export function createPlaygroundDraft(config: Scenario): PlaygroundDraft {
  return {
    mechanism: "credits",
    rounds: 1,
    seats: 1,
    seed: 1,
    // O playground é um leilão isolado, com uma distribuição só: parte do
    // primeiro perfil de desempenho do cenário, e dali o usuário mexe à
    // vontade. Aqui não há população com grupos a separar.
    modeGrade: config.performance_profiles[0]?.mode_grade ?? 8,
    zeroRate: config.performance_profiles[0]?.zero_rate ?? 0.005,
    maxRate: config.performance_profiles[0]?.max_rate ?? 0.008,
    selected: 0,
    students: [newStudent("voce", "Você", config)],
  };
}

interface OfferedClass {
  name: string;
  discipline: string;
  hours: number;
}

/** As turmas do cenário, na ordem da grade. Espelha
 * `SimulationConfig.classes_of`: turma única tem o nome da disciplina, e as
 * demais ganham o sufixo " T1", " T2"… */
function offeredClasses(disciplines: DisciplineInput[]): OfferedClass[] {
  return disciplines.flatMap(({ name, hours, classes }) =>
    (classes ?? 1) <= 1
      ? [{ name, discipline: name, hours }]
      : Array.from({ length: classes }, (_, i) => ({
          name: `${name} T${i + 1}`,
          discipline: name,
          hours,
        }))
  );
}

function newStudent(id: string, label: string, config: Scenario): PlaygroundStudent {
  return {
    id,
    label,
    credits: config.base_credits,
    cr: 7,
    maxHours: config.max_hours,
    // Disponibilidade que cobre a carga e os dois valores neutros: o aluno
    // novo não exclui nada e manda a mensagem sincera, como o `Student`
    // construído à mão no motor.
    availability: config.max_hours,
    selectivity: 0,
    concentration: 1,
    rows: {},
  };
}

export function Playground({
  config,
  draft,
  setDraft,
}: {
  config: Scenario;
  draft: PlaygroundDraft;
  setDraft: (draft: PlaygroundDraft) => void;
}) {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PlaygroundResponse | null>(null);
  const [toAdd, setToAdd] = useState("");
  const [utility, setUtility] = useState(1);
  const selected = draft.students[draft.selected] ?? draft.students[0];
  const auction = draft.mechanism === "credits";
  const offer = offeredClasses(config.disciplines);
  const listed = Object.keys(selected.rows)
    .map((name) => offer.find((offered) => offered.name === name))
    .filter((offered): offered is OfferedClass => offered !== undefined);
  const remaining = offer.filter((offered) => selected.rows[offered.name] === undefined);
  const adding = remaining.find((offered) => offered.name === toAdd) ?? remaining[0];

  function patchStudent(update: (student: PlaygroundStudent) => PlaygroundStudent) {
    setDraft({
      ...draft,
      students: draft.students.map((student) =>
        student.id === selected.id ? update(student) : student
      ),
    });
  }

  function addDiscipline() {
    if (!adding || !(utility > 0)) return;
    patchStudent((student) => ({
      ...student,
      rows: { ...student.rows, [adding.name]: utility },
    }));
  }

  function setUtilityOf(name: string, value: number) {
    patchStudent((student) => ({ ...student, rows: { ...student.rows, [name]: value } }));
  }

  function removeDiscipline(name: string) {
    patchStudent((student) => {
      const rows = { ...student.rows };
      delete rows[name];
      return { ...student, rows };
    });
  }

  async function run() {
    setRunning(true);
    setError(null);
    try {
      setResult(
        await playground({
          mechanism: draft.mechanism,
          rounds: draft.rounds,
          seed: draft.seed,
          mode_grade: draft.modeGrade,
          zero_rate: draft.zeroRate,
          max_rate: draft.maxRate,
          classes: offer.map(({ name, discipline, hours }) => ({
            name,
            discipline,
            seats: draft.seats ?? 1,
            hours,
          })),
          students: draft.students.map((student) => {
            const eligible = offer
              .filter((offered) => student.rows[offered.name] !== undefined)
              .map((offered) => offered.name);
            return {
              id: student.id,
              credits: student.credits,
              cr: student.cr,
              max_hours: student.maxHours,
              utilities: Object.fromEntries(eligible.map((name) => [name, student.rows[name]])),
              eligible,
              availability: student.availability ?? student.maxHours,
              selectivity: student.selectivity ?? 0,
              concentration: student.concentration ?? 1,
            };
          }),
        })
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <h1>Submochila</h1>
      {error && <div className="error-banner">{error}</div>}

      <div className="panel">
        <div className="field-row">
          <div className="field">
            <label>Mecanismo</label>
            <select
              value={draft.mechanism}
              onChange={(e) => setDraft({ ...draft, mechanism: e.target.value as Mechanism })}
            >
              <option value="credits">leilão</option>
              <option value="ranking">CR</option>
            </select>
          </div>
          <div className="field">
            <label>Rodadas</label>
            <input
              type="number"
              min={1}
              max={10}
              value={draft.rounds}
              onChange={(e) => setDraft({ ...draft, rounds: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label>Vagas por turma</label>
            <input
              type="number"
              min={1}
              value={draft.seats ?? 1}
              onChange={(e) => setDraft({ ...draft, seats: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label>Nota mais provável</label>
            <input
              type="number"
              min={0.1}
              max={9.9}
              step={0.1}
              value={draft.modeGrade}
              onChange={(e) => setDraft({ ...draft, modeGrade: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label>Chance de 0 (%)</label>
            <input
              type="number"
              min={0.01}
              max={99}
              step={0.01}
              value={Math.round(draft.zeroRate * 1e6) / 1e4}
              onChange={(e) =>
                setDraft({ ...draft, zeroRate: Number(e.target.value) / 100 })
              }
            />
          </div>
          <div className="field">
            <label>Chance de 10 (%)</label>
            <input
              type="number"
              min={0.01}
              max={99}
              step={0.01}
              value={Math.round(draft.maxRate * 1e6) / 1e4}
              onChange={(e) =>
                setDraft({ ...draft, maxRate: Number(e.target.value) / 100 })
              }
            />
          </div>
          <div className="field">
            <label>Seed</label>
            <input
              type="number"
              value={draft.seed}
              onChange={(e) => setDraft({ ...draft, seed: Number(e.target.value) })}
            />
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="chips">
          {draft.students.map((student, index) => (
            <button
              key={student.id}
              className={`chip ${student.id === selected.id ? "on" : "off"}`}
              onClick={() => setDraft({ ...draft, selected: index })}
            >
              {student.label}
            </button>
          ))}
          <button
            className="secondary"
            onClick={() => {
              let index = draft.students.length + 1;
              while (draft.students.some((student) => student.id === `aluno-${index}`)) index += 1;
              setDraft({
                ...draft,
                selected: draft.students.length,
                students: [
                  ...draft.students,
                  newStudent(`aluno-${index}`, `Aluno ${index}`, config),
                ],
              });
            }}
          >
            + aluno
          </button>
          <button
            className="danger"
            disabled={draft.students.length === 1}
            onClick={() => {
              const students = draft.students.filter((student) => student.id !== selected.id);
              setDraft({ ...draft, students, selected: 0 });
            }}
          >
            remover
          </button>
        </div>

        <div className="field-row">
          {auction ? (
            <div className="field">
              <label>Créditos</label>
              <input
                type="number"
                min={0}
                value={selected.credits}
                onChange={(e) =>
                  patchStudent((student) => ({ ...student, credits: Number(e.target.value) }))
                }
              />
            </div>
          ) : (
            <div className="field">
              <label>CR</label>
              <input
                type="number"
                step={0.1}
                value={selected.cr}
                onChange={(e) =>
                  patchStudent((student) => ({ ...student, cr: Number(e.target.value) }))
                }
              />
            </div>
          )}
          <div className="field">
            <label>Carga horária máxima</label>
            <input
              type="number"
              min={1}
              value={selected.maxHours}
              onChange={(e) =>
                patchStudent((student) => ({ ...student, maxHours: Number(e.target.value) }))
              }
            />
          </div>
          <div className="field">
            <label>CH disponível</label>
            <input
              type="number"
              min={0}
              value={selected.availability ?? selected.maxHours}
              onChange={(e) =>
                patchStudent((student) => ({ ...student, availability: Number(e.target.value) }))
              }
            />
          </div>
          <div className="field">
            <label>Seletividade</label>
            <input
              type="number"
              min={0}
              step={0.125}
              list="submochila-seletividade"
              value={selected.selectivity ?? 0}
              onChange={(e) =>
                patchStudent((student) => ({ ...student, selectivity: Number(e.target.value) }))
              }
            />
            <datalist id="submochila-seletividade">
              {config.selectivity_profiles.map((profile) => (
                <option key={profile.name} value={profile.value} label={profile.name} />
              ))}
            </datalist>
          </div>
          <div className="field">
            <label>Concentração</label>
            <input
              type="number"
              min={-3}
              max={5}
              step={0.5}
              list="submochila-concentracao"
              value={selected.concentration ?? 1}
              onChange={(e) =>
                patchStudent((student) => ({ ...student, concentration: Number(e.target.value) }))
              }
            />
            <datalist id="submochila-concentracao">
              {config.concentration_profiles.map((profile) => (
                <option key={profile.name} value={profile.value} label={profile.name} />
              ))}
            </datalist>
          </div>
        </div>

        {adding && (
          <div className="field-row">
            <div className="field grow">
              <label>Turma</label>
              <select value={adding.name} onChange={(e) => setToAdd(e.target.value)}>
                {remaining.map((offered) => (
                  <option key={offered.name} value={offered.name}>
                    {offered.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Utilidade</label>
              <input
                type="number"
                min={0.01}
                step={0.1}
                value={utility}
                onChange={(e) => setUtility(Number(e.target.value))}
              />
            </div>
            <button className="secondary" disabled={!(utility > 0)} onClick={addDiscipline}>
              adicionar
            </button>
          </div>
        )}

        {listed.length === 0 ? (
          <p className="empty-state">Nenhuma disciplina.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Turma</th>
                <th style={{ width: 80 }}>Carga</th>
                <th style={{ width: 120 }}>Utilidade</th>
                <th style={{ width: 90 }} />
              </tr>
            </thead>
            <tbody>
              {listed.map((offered) => (
                <tr key={offered.name}>
                  <td>{offered.name}</td>
                  <td className="muted-cell">{offered.hours} h</td>
                  <td>
                    <input
                      type="number"
                      min={0.01}
                      step={0.1}
                      value={selected.rows[offered.name]}
                      onChange={(e) => setUtilityOf(offered.name, Number(e.target.value))}
                    />
                  </td>
                  <td>
                    <button className="link" onClick={() => removeDiscipline(offered.name)}>
                      remover
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="actions">
          <button className="primary" disabled={running || config.disciplines.length === 0} onClick={run}>
            {running ? "Rodando..." : "Rodar"}
          </button>
        </div>
      </div>

      {result && (
        <PlaygroundResult
          result={result}
          labels={draft.students}
          auction={auction}
          hours={Object.fromEntries(offer.map(({ name, hours }) => [name, hours]))}
        />
      )}
    </div>
  );
}

function roundStatus(
  student: { bids: Record<string, number>; won: string[] },
  name: string,
): { label: string; className: string } {
  if (student.bids[name] === undefined) return { label: "Não solicitada", className: "unbid" };
  if (student.won.includes(name)) return { label: "Deferida", className: "won" };
  return { label: "Indeferida", className: "refused" };
}

function formatUtility(value: number | undefined): string {
  if (value === undefined) return "—";
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 3 });
}

function PlaygroundResult({
  result,
  labels,
  auction,
  hours,
}: {
  result: PlaygroundResponse;
  labels: { id: string; label: string }[];
  auction: boolean;
  hours: Record<string, number>;
}) {
  const label = (id: string) => labels.find((student) => student.id === id)?.label ?? id;
  const grades = new Map(
    result.grades.map((grade) => [`${grade.student_id}\u0000${grade.name}`, grade.grade])
  );
  // A ordem da grade, que é a mesma das duas listas: cursadas e excluídas
  // intercaladas como a disciplina aparece no cenário.
  const closing = result.closing
    .map((row) => ({
      ...row,
      obtained: Object.keys(hours).filter(
        (name) => row.retained.includes(name) || row.excluded.includes(name)
      ),
      taken: row.retained.reduce((sum, name) => sum + (hours[name] ?? 0), 0),
    }))
    .filter((row) => row.obtained.length > 0);
  return (
    <>
      {result.rounds.map((round) => (
        <div className="panel" key={round.number}>
          <h2>Rodada {round.number}</h2>
          <table>
            <thead>
              <tr>
                <th>Aluno</th>
                <th>Resultado</th>
                <th>Turma</th>
                <th>Utilidade</th>
                {auction && <th>Lance</th>}
                {auction && <th>Preço</th>}
                <th>Carga restante</th>
                {auction && <th>Créditos restantes</th>}
              </tr>
            </thead>
            <tbody>
              {round.students.map((student) => {
                const names = [
                  ...Object.keys(student.utilities),
                  ...Object.keys(student.bids).filter((name) => student.utilities[name] === undefined),
                ];
                const lines = names.length > 0 ? names : [null];
                return lines.map((name, index) => {
                  const status = name === null ? null : roundStatus(student, name);
                  const requested = name !== null && student.bids[name] !== undefined;
                  return (
                    <tr key={`${student.id}-${name ?? "vazio"}`}>
                      {index === 0 && <td rowSpan={lines.length}>{label(student.id)}</td>}
                      <td className={status ? `outcome ${status.className}` : undefined}>
                        {status?.label ?? "—"}
                      </td>
                      <td>{name ?? "—"}</td>
                      <td>{name ? formatUtility(student.utilities[name]) : "—"}</td>
                      {auction && <td>{requested ? student.bids[name!] : "—"}</td>}
                      {auction && (
                        <td>{requested && round.prices ? (round.prices[name!] ?? "—") : "—"}</td>
                      )}
                      {index === 0 && (
                        <td rowSpan={lines.length}>{student.remaining_hours} h</td>
                      )}
                      {auction && index === 0 && (
                        <td rowSpan={lines.length}>{student.remaining_credits}</td>
                      )}
                    </tr>
                  );
                });
              })}
            </tbody>
          </table>
        </div>
      ))}
      <div className="panel">
        <h2>Fechamento</h2>
        {closing.length === 0 ? (
          <p className="empty-state">Nenhuma disciplina conquistada.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Aluno</th>
                <th>Situação</th>
                <th>Turma</th>
                <th>Nota</th>
                <th>CH disponível</th>
                <th>CH cursada</th>
              </tr>
            </thead>
            <tbody>
              {closing.map((row) =>
                row.obtained.map((name, index) => {
                  const excluded = row.excluded.includes(name);
                  const grade = grades.get(`${row.student_id}\u0000${name}`);
                  return (
                    <tr key={`${row.student_id}-${name}`}>
                      {index === 0 && <td rowSpan={row.obtained.length}>{label(row.student_id)}</td>}
                      <td>
                        <span className={`outcome ${excluded ? "dropped" : "approved"}`}>
                          {excluded ? "Excluída" : "Cursada"}
                        </span>
                      </td>
                      <td>{name}</td>
                      <td>{grade === undefined ? "—" : grade.toLocaleString("pt-BR")}</td>
                      {index === 0 && (
                        <td rowSpan={row.obtained.length}>
                          {row.load === null ? "—" : `${row.load} h`}
                        </td>
                      )}
                      {index === 0 && <td rowSpan={row.obtained.length}>{row.taken} h</td>}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

