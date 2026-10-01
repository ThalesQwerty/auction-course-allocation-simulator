import { describeRun, formatRunDate, SimulationRun } from "./history";

export type View = { kind: "config" } | { kind: "project" } | { kind: "run"; id: string };

export function Sidebar({
  view,
  history,
  onNavigate,
  onDelete,
  onClear,
}: {
  view: View;
  history: SimulationRun[];
  onNavigate: (view: View) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
}) {
  const key = (v: View) => (v.kind === "run" ? `run:${v.id}` : v.kind);
  const selected = (target: View) => key(view) === key(target);

  return (
    <nav className="sidebar" aria-label="Navegação">
      <div className="sidebar-brand">
        Leilão por créditos
        <span>simulador de matrícula</span>
      </div>

      <ul className="nav-list">
        <li>
          <button className={`nav-item ${selected({ kind: "config" }) ? "current" : ""}`} onClick={() => onNavigate({ kind: "config" })}>
            Configurar
          </button>
        </li>
        <li>
          <button className={`nav-item ${selected({ kind: "project" }) ? "current" : ""}`} onClick={() => onNavigate({ kind: "project" })}>
            Projeto
          </button>
        </li>
      </ul>

      <div className="sidebar-section">
        <h2>Simulações</h2>
        {history.length === 0 ? (
          <p className="sidebar-empty">Nenhuma simulação executada ainda.</p>
        ) : (
          <ul className="nav-list">
            {history.map((run) => (
              <li key={run.id} className="nav-row">
                <button
                  className={`nav-item run ${selected({ kind: "run", id: run.id }) ? "current" : ""}`}
                  onClick={() => onNavigate({ kind: "run", id: run.id })}
                  title={describeRun(run)}
                >
                  {formatRunDate(run.at)}
                  <span>{describeRun(run)}</span>
                </button>
                <button
                  className="nav-delete"
                  onClick={() => onDelete(run.id)}
                  title={`Apagar a simulação de ${formatRunDate(run.at)}`}
                  aria-label={`Apagar a simulação de ${formatRunDate(run.at)}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="sidebar-footer">
        <button className="nav-item danger" onClick={onClear} disabled={history.length === 0}>
          Limpar histórico
        </button>
      </div>
    </nav>
  );
}
