import { useState } from "react";
import { playground } from "./api";
import type { DisciplineInput, Mechanism, PlaygroundResponse, Scenario } from "./types";

interface PlaygroundStudent {
  id: string;
  label: string;
  credits: number;
  cr: number;
  maxHours: number;
  rows: Record<string, number>;
}

export interface PlaygroundDraft {
  mechanism: Mechanism;
  rounds: number;
  seats: number;
  seed: number;
  aptitudeMean: number;
  aptitudeConcentration: number;
  selected: number;
  students: PlaygroundStudent[];
}

export function createPlaygroundDraft(config: Scenario): PlaygroundDraft {
  return {
    mechanism: "credits",
    rounds: 1,
    seats: 1,
    seed: 1,
    aptitudeMean: config.aptitude_mean,
    aptitudeConcentration: config.aptitude_concentration,
    selected: 0,
    students: [newStudent("voce", "Você", config)],
  };
}

function newStudent(id: string, label: string, config: Scenario): PlaygroundStudent {
  return {
    id,
    label,
    credits: config.base_credits,
    cr: 7,
    maxHours: config.max_hours,
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
  const listed = Object.keys(selected.rows)
    .map((name) => config.disciplines.find((discipline) => discipline.name === name))
    .filter((discipline): discipline is DisciplineInput => discipline !== undefined);
  const remaining = config.disciplines.filter((discipline) => selected.rows[discipline.name] === undefined);
  const adding = remaining.find((discipline) => discipline.name === toAdd) ?? remaining[0];

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
          aptitude_mean: draft.aptitudeMean,
          aptitude_concentration: draft.aptitudeConcentration,
          disciplines: config.disciplines.map(({ name, hours }) => ({
            name,
            seats: draft.seats ?? 1,
            hours,
          })),
          students: draft.students.map((student) => {
            const eligible = config.disciplines
              .filter((discipline) => student.rows[discipline.name] !== undefined)
              .map((discipline) => discipline.name);
            return {
              id: student.id,
              credits: student.credits,
              cr: student.cr,
              max_hours: student.maxHours,
              utilities: Object.fromEntries(eligible.map((name) => [name, student.rows[name]])),
              eligible,
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
            <label>Vagas por disciplina</label>
            <input
              type="number"
              min={1}
              value={draft.seats ?? 1}
              onChange={(e) => setDraft({ ...draft, seats: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label>Aptidão: média</label>
            <input
              type="number"
              min={0.01}
              max={0.99}
              step={0.01}
              value={draft.aptitudeMean}
              onChange={(e) => setDraft({ ...draft, aptitudeMean: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label>Aptidão: concentração</label>
            <input
              type="number"
              min={0.1}
              step={0.5}
              value={draft.aptitudeConcentration}
              onChange={(e) =>
                setDraft({ ...draft, aptitudeConcentration: Number(e.target.value) })
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
        </div>

        {adding && (
          <div className="field-row">
            <div className="field grow">
              <label>Disciplina</label>
              <select value={adding.name} onChange={(e) => setToAdd(e.target.value)}>
                {remaining.map((discipline) => (
                  <option key={discipline.name} value={discipline.name}>
                    {discipline.name}
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
                <th>Disciplina</th>
                <th style={{ width: 80 }}>Carga</th>
                <th style={{ width: 120 }}>Utilidade</th>
                <th style={{ width: 90 }} />
              </tr>
            </thead>
            <tbody>
              {listed.map((discipline) => (
                <tr key={discipline.name}>
                  <td>{discipline.name}</td>
                  <td className="muted-cell">{discipline.hours} h</td>
                  <td>
                    <input
                      type="number"
                      min={0.01}
                      step={0.1}
                      value={selected.rows[discipline.name]}
                      onChange={(e) => setUtilityOf(discipline.name, Number(e.target.value))}
                    />
                  </td>
                  <td>
                    <button className="link" onClick={() => removeDiscipline(discipline.name)}>
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

      {result && <PlaygroundResult result={result} labels={draft.students} auction={auction} />}
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
}: {
  result: PlaygroundResponse;
  labels: { id: string; label: string }[];
  auction: boolean;
}) {
  const label = (id: string) => labels.find((student) => student.id === id)?.label ?? id;
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
                <th>Disciplina</th>
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
        <h2>Notas</h2>
        {result.grades.length === 0 ? (
          <p className="empty-state">Nenhuma disciplina conquistada.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Aluno</th>
                <th>Disciplina</th>
                <th>Nota</th>
              </tr>
            </thead>
            <tbody>
              {result.grades.map((grade) => (
                <tr key={`${grade.student_id}-${grade.discipline}`}>
                  <td>{label(grade.student_id)}</td>
                  <td>{grade.discipline}</td>
                  <td>{grade.grade.toLocaleString("pt-BR")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

