import { useEffect, useMemo, useState } from "react";
import {
  disciplineIndex,
  disciplineTrace,
  studentIndex,
  studentTrace,
} from "../api";
import type { ComparisonRun } from "../history";
import { COMPARISON_ARMS } from "../types";
import type {
  DisciplineIndexPayload,
  DisciplineTracePayload,
  StudentIndexPayload,
  StudentTracePayload,
} from "../types";
import { DisciplineHistory } from "./DisciplineHistory";
import { DisciplineIndex } from "./DisciplineIndex";
import { StudentHistory } from "./StudentHistory";
import { StudentIndex } from "./StudentIndex";

type View = "students" | "disciplines";

export function Trace({ run }: { run: ComparisonRun }) {
   /** Só os braços que esta comparação de fato rodou: uma gravada antes de um braço existir não o traz, e pedir o histórico dele não encontraria simulação */
  const arms = useMemo(
    () => COMPARISON_ARMS.filter((arm) => run.arms.includes(arm.key)),
    [run.arms]
  );

  const first = run.config.first_seed ?? 1;
  const last = first + run.seeds - 1;

  const [armKey, setArmKey] = useState(
    arms[arms.length - 1]?.key ?? COMPARISON_ARMS[0].key
  );
  const [typed, setTyped] = useState(String(first));
  const [view, setView] = useState<View>("students");
  const [student, setStudent] = useState<string | null>(null);
  const [discipline, setDiscipline] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const [students, setStudents] = useState<StudentIndexPayload | null>(null);
  const [disciplines, setDisciplines] = useState<DisciplineIndexPayload | null>(
    null
  );
  const [history, setHistory] = useState<StudentTracePayload | null>(null);
  const [offer, setOffer] = useState<DisciplineTracePayload | null>(null);
  const [loadingIndex, setLoadingIndex] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const seed = Number(typed);
  const valid = Number.isInteger(seed) && seed >= first && seed <= last;

  useEffect(() => {
    if (!valid) return;
    let cancelled = false;
    setLoadingIndex(true);
    setError(null);
    const wanted =
      view === "students"
        ? studentIndex(run.id, armKey, seed).then((payload) => {
            if (!cancelled) setStudents(payload);
          })
        : disciplineIndex(run.id, armKey, seed).then((payload) => {
            if (!cancelled) setDisciplines(payload);
          });
    wanted
      .catch((failure: Error) => {
        if (cancelled) return;
        setError(failure.message);
        if (view === "students") setStudents(null);
        else setDisciplines(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingIndex(false);
      });
    return () => {
      cancelled = true;
    };
  }, [run.id, armKey, seed, valid, view, attempt]);

  useEffect(() => {
    const chosen = view === "students" ? student : discipline;
    if (!valid || !chosen) return;
    let cancelled = false;
    setLoadingDetail(true);
    const wanted =
      view === "students"
        ? studentTrace(run.id, chosen, armKey, seed).then((payload) => {
            if (!cancelled) setHistory(payload);
          })
        : disciplineTrace(run.id, chosen, armKey, seed).then((payload) => {
            if (!cancelled) setOffer(payload);
          });
    wanted
      .catch((failure: Error) => {
        if (cancelled) return;
        setError(failure.message);
        if (view === "students") setHistory(null);
        else setOffer(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });
    return () => {
      cancelled = true;
    };
  }, [run.id, armKey, seed, valid, view, student, discipline, attempt]);

   /** O mecanismo do braço **carregado**, e não o do seletor: as colunas de crédito descrevem o que está na tela */
  const loaded = view === "students" ? students?.braco : disciplines?.braco;
  const usesCredits =
    COMPARISON_ARMS.find((arm) => arm.key === loaded)?.mechanism !== "ranking";

  return (
    <section className="chart-section">
      <header className="chart-section-head">
        <h2>Histórico de um aluno ou de uma disciplina</h2>
      </header>

      <div className="panel trace-controls">
        <div className="field-row">
          <div className="field">
            <label htmlFor="trace-arm">Modelo</label>
            <select
              id="trace-arm"
              value={armKey}
              onChange={(event) => setArmKey(event.target.value)}
            >
              {arms.map((arm) => (
                <option key={arm.key} value={arm.key}>
                  {arm.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="trace-seed">Simulação (seed)</label>
            <input
              id="trace-seed"
              type="number"
              min={first}
              max={last}
              step={1}
              className={valid ? undefined : "invalid"}
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
            />
            {!valid && (
              <p className="field-error">
                de {first} a {last}
              </p>
            )}
          </div>
          <div className="field">
            <label>O que ver</label>
            <div className="view-switch">
              <button
                type="button"
                className={view === "students" ? "on" : ""}
                onClick={() => setView("students")}
              >
                Alunos
              </button>
              <button
                type="button"
                className={view === "disciplines" ? "on" : ""}
                onClick={() => setView("disciplines")}
              >
                Disciplinas
              </button>
            </div>
          </div>
          {error && (
            <div className="field">
              <label>&nbsp;</label>
              <button type="button" onClick={() => setAttempt((n) => n + 1)}>
                Tentar de novo
              </button>
            </div>
          )}
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {(loadingIndex || loadingDetail) && (
        <p className="empty-state">Carregando…</p>
      )}

      {view === "students" && students && (
        <>
          <div hidden={Boolean(student)}>
            <StudentIndex
              payload={students}
              usesCredits={usesCredits}
              escolhido={student ?? undefined}
              aoEscolher={(row) => setStudent(row.aluno)}
            />
          </div>
          {student && history && (
            <StudentHistory
              payload={history}
              rounds={run.config.rounds}
              usesCredits={usesCredits}
              aoVoltar={() => {
                setStudent(null);
                setHistory(null);
              }}
            />
          )}
        </>
      )}

      {view === "disciplines" && disciplines && (
        <>
          <div hidden={Boolean(discipline)}>
            <DisciplineIndex
              payload={disciplines}
              usesCredits={usesCredits}
              escolhido={discipline ?? undefined}
              aoEscolher={(row) => setDiscipline(row.disciplina)}
            />
          </div>
          {discipline && offer && (
            <DisciplineHistory
              payload={offer}
              rounds={run.config.rounds}
              usesCredits={usesCredits}
              aoVoltar={() => {
                setDiscipline(null);
                setOffer(null);
              }}
            />
          )}
        </>
      )}
    </section>
  );
}
