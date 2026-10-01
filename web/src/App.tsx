import { useEffect, useState } from "react";
import { simulate } from "./api";
import { Config } from "./Config";
import { choosePreset, editConfig, initialChoice, PresetChoice } from "./presets";
import { formatRunDate, loadHistory, MAX_RUNS, newRun, saveHistory, SimulationRun } from "./history";
import { Project } from "./Project";
import { Results } from "./Results";
import { Sidebar, View } from "./Sidebar";

export default function App() {
  const [choice, setChoice] = useState<PresetChoice>(initialChoice);
  const config = choice.config;
  const [history, setHistory] = useState<SimulationRun[]>(loadHistory);
  const [view, setView] = useState<View>({ kind: "config" });
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loadingHistories, setLoadingHistories] = useState(false);
  const [historiesError, setHistoriesError] = useState<string | null>(null);

  // O histórico mora no navegador: execuções antigas sobrevivem a um recarregamento.
  useEffect(() => {
    const kept = saveHistory(history);
    if (kept.length !== history.length) setHistory(kept);
  }, [history]);

  function navigate(next: View) {
    setView(next);
    setMenuOpen(false);
  }

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const run = newRun(config, await simulate(config));
      setHistory((current) => [run, ...current].slice(0, MAX_RUNS));
      navigate({ kind: "run", id: run.id });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  /** Reconstrói o detalhe por aluno de uma execução antiga: ele não é
   * persistido (ver `history.ts`), mas a simulação é determinística pela seed,
   * então reexecutar devolve exatamente o mesmo resultado. */
  async function loadHistories(run: SimulationRun) {
    setLoadingHistories(true);
    setHistoriesError(null);
    try {
      const result = await simulate(run.config, true);
      setHistory((current) => current.map((r) => (r.id === run.id ? { ...r, result } : r)));
    } catch (e) {
      setHistoriesError((e as Error).message);
    } finally {
      setLoadingHistories(false);
    }
  }

  function handleDelete(id: string) {
    const run = history.find((r) => r.id === id);
    if (!run) return;
    if (!confirm(`Apagar a simulação de ${formatRunDate(run.at)}? A ação não pode ser desfeita.`)) return;
    setHistory((current) => current.filter((r) => r.id !== id));
    // Se a execução apagada era a que estava na tela, volta para a configuração.
    if (view.kind === "run" && view.id === id) navigate({ kind: "config" });
  }

  function handleClear() {
    if (!confirm("Apagar todas as simulações guardadas? A ação não pode ser desfeita.")) return;
    setHistory([]);
    navigate({ kind: "config" });
  }

  // Uma execução apagada pelo limite de espaço cai de volta na configuração
  // em vez de deixar a tela em branco.
  const current = view.kind === "run" ? history.find((run) => run.id === view.id) : undefined;
  const showConfig = view.kind === "config" || (view.kind === "run" && !current);

  return (
    <div className={`shell ${menuOpen ? "menu-open" : ""}`}>
      <button className="menu-toggle" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen}>
        {menuOpen ? "fechar" : "menu"}
      </button>

      <Sidebar view={view} history={history} onNavigate={navigate} onDelete={handleDelete} onClear={handleClear} />

      <main className="main wide">
        {showConfig && (
          <Config
            config={config}
            setConfig={(update) => setChoice((c) => editConfig(c, update(c.config)))}
            running={running}
            error={error}
            onRun={handleRun}
            presetId={choice.presetId}
            hasCustom={choice.custom !== null}
            onSelectPreset={(id) => {
              setChoice((c) => choosePreset(c, id));
              setError(null);
            }}
          />
        )}
        {view.kind === "project" && <Project />}
        {current && (
          <Results
            key={current.id}
            run={current}
            onReuseConfig={() => {
              setChoice((c) => editConfig(c, current.config));
              setError(null);
              navigate({ kind: "config" });
            }}
            histories={{
              loading: loadingHistories,
              error: historiesError,
              load: () => loadHistories(current),
            }}
          />
        )}
      </main>
    </div>
  );
}
