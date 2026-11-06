import { describeEntry, formatRunDate, HistoryEntry } from "./history";

export type View =
  | { kind: "config" }
  | { kind: "project" }
  | { kind: "graph" }
  | { kind: "playground" }
  | { kind: "run"; id: string };

export function Sidebar({
  view,
  history,
  onNavigate,
  onDelete,
  onClear,
  onLoadFile,
}: {
  view: View;
  history: HistoryEntry[];
  onNavigate: (view: View) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
  /** Um resultado gravado em disco pela API, de volta para a lista. */
  onLoadFile: (file: File) => void;
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
        <li>
          <button className={`nav-item ${selected({ kind: "graph" }) ? "current" : ""}`} onClick={() => onNavigate({ kind: "graph" })}>
            Grade
          </button>
        </li>
        <li>
          <button className={`nav-item ${selected({ kind: "playground" }) ? "current" : ""}`} onClick={() => onNavigate({ kind: "playground" })}>
            Submochila
          </button>
        </li>
      </ul>

      <div className="sidebar-section">
        <h2>Execuções</h2>
        {history.length === 0 ? (
          <p className="sidebar-empty">Nada executado ainda.</p>
        ) : (
          <ul className="nav-list">
            {history.map((entry) => (
              <li key={entry.id} className="nav-row">
                <button
                  className={`nav-item run ${selected({ kind: "run", id: entry.id }) ? "current" : ""}`}
                  onClick={() => onNavigate({ kind: "run", id: entry.id })}
                  title={describeEntry(entry)}
                >
                  {formatRunDate(entry.at)}
                  <span>{describeEntry(entry)}</span>
                </button>
                <button
                  className="nav-delete"
                  onClick={() => onDelete(entry.id)}
                  title={`Apagar a execução de ${formatRunDate(entry.at)}`}
                  aria-label={`Apagar a execução de ${formatRunDate(entry.at)}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="sidebar-footer">
        <label className="nav-item file-item">
          Carregar resultado
          <input
            type="file"
            accept="application/json,.json"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onLoadFile(file);
              // Zera para que carregar o mesmo arquivo duas vezes seguidas
              // dispare o evento nas duas.
              e.target.value = "";
            }}
          />
        </label>
        <button className="nav-item danger" onClick={onClear} disabled={history.length === 0}>
          Limpar histórico
        </button>
      </div>
    </nav>
  );
}
