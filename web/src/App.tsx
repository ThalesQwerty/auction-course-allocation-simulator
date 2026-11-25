import { useEffect, useState } from "react";
import { compare } from "./api";
import { Comparison } from "./Comparison";
import { Config } from "./Config";
import { choosePreset, editConfig, initialChoice, PresetChoice } from "./presets";
import {
  loadSavedPresets,
  saveSavedPresets,
  upsertSavedPreset,
} from "./savedPresets";
import {
  formatRunDate,
  HistoryEntry,
  loadHistory,
  MAX_RUNS,
  entryFromFile,
  newComparison,
  saveHistory,
} from "./history";
import type { ComparisonRun } from "./history";
import { GradeGraph } from "./GradeGraph";
import { createPlaygroundDraft, Playground, PlaygroundDraft } from "./Playground";
import { Sidebar, View } from "./Sidebar";
import { COMPARISON_ARMS } from "./types";
import type { CompareRequest } from "./types";

export default function App() {
  const [choice, setChoice] = useState<PresetChoice>(initialChoice);
  const [saved, setSaved] = useState(loadSavedPresets);
  const config = choice.config;
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [view, setView] = useState<View>({ kind: "config" });
  const [playground, setPlayground] = useState<PlaygroundDraft | null>(null);
  const [runs, setRuns] = useState(20);
  const [arms, setArms] = useState<string[]>(() => COMPARISON_ARMS.map((arm) => arm.key));
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    loadHistory().then((stored) => {
      if (!alive) return;
      setHistory((current) => [...current, ...stored].slice(0, MAX_RUNS));
      setLoaded(true);
    });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!loaded) return;
    let alive = true;
    saveHistory(history).then((kept) => {
      if (alive && kept.length !== history.length) setHistory(kept);
    });
    return () => {
      alive = false;
    };
  }, [history, loaded]);

   /** Carrega um resultado gravado em disco e o abre */
  async function handleLoadFile(file: File) {
    setError(null);
    try {
      const entry = entryFromFile(await file.text());
      setHistory((current) => [entry, ...current].slice(0, MAX_RUNS));
      navigate({ kind: "run", id: entry.id });
    } catch (e) {
      setError(`não foi possível ler ${file.name}: ${(e as Error).message}`);
      navigate({ kind: "config" });
    }
  }

  function navigate(next: View) {
    setView(next);
    setMenuOpen(false);
  }

   /** Roda a comparação e abre o resultado */
  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const { seed: _seed, ...scenario } = config;
      const request = { ...scenario, runs, arms };
      const entry = newComparison(request, await compare(request));
      setHistory((current) => [entry, ...current].slice(0, MAX_RUNS));
      navigate({ kind: "run", id: entry.id });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

   /** Roda de novo a mesma execução com outros pontos de corte */
  async function handleRecut(entry: ComparisonRun, cuts: Partial<CompareRequest>) {
    setRunning(true);
    setError(null);
    try {
      const request = { ...entry.config, ...cuts };
      const next = newComparison(request, await compare(request));
      setHistory((current) => [next, ...current].slice(0, MAX_RUNS));
      navigate({ kind: "run", id: next.id });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  function handleDelete(id: string) {
    const entry = history.find((e) => e.id === id);
    if (!entry) return;
    if (!confirm(`Apagar a execução de ${formatRunDate(entry.at)}? A ação não pode ser desfeita.`))
      return;
    setHistory((current) => current.filter((e) => e.id !== id));
    if (view.kind === "run" && view.id === id) navigate({ kind: "config" });
  }

  function handleClear() {
    if (!confirm("Apagar todas as execuções guardadas? A ação não pode ser desfeita.")) return;
    setHistory([]);
    navigate({ kind: "config" });
  }

   /** Volta ao formulário com o cenário de uma execução carregado */
  function reuseConfig(entry: HistoryEntry) {
    const { runs: count, arms: chosen, ...scenario } = entry.config;
    setChoice((c) => editConfig(c, { ...c.config, ...scenario }));
    setRuns(count);
    setArms(chosen ?? COMPARISON_ARMS.map((arm) => arm.key));
    setError(null);
    navigate({ kind: "config" });
  }


  const current = view.kind === "run" ? history.find((entry) => entry.id === view.id) : undefined;
  const showConfig = view.kind === "config" || (view.kind === "run" && !current);

  return (
    <div className={`shell ${menuOpen ? "menu-open" : ""}`}>
      <button className="menu-toggle" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen}>
        {menuOpen ? "fechar" : "menu"}
      </button>

      <Sidebar
        view={view}
        history={history}
        onNavigate={navigate}
        onDelete={handleDelete}
        onClear={handleClear}
        onLoadFile={handleLoadFile}
      />

      <main className="main wide">
        {showConfig && (
          <Config
            config={config}
            setConfig={(update) => setChoice((c) => editConfig(c, update(c.config)))}
            runs={runs}
            setRuns={setRuns}
            arms={arms}
            setArms={setArms}
            running={running}
            error={error}
            onRun={handleRun}
            presetId={choice.presetId}
            hasCustom={choice.custom !== null}
            onSelectPreset={(id) => {
              setChoice((c) => choosePreset(c, id, saved));
              setError(null);
            }}
            saved={saved}
            onSave={(name) => {
              const next = saveSavedPresets(upsertSavedPreset(saved, name, config));
              setSaved(next);
              const stored = next.find((entry) => entry.name === name.trim());
              if (stored) setChoice((c) => ({ ...c, presetId: stored.id }));
            }}
            onDeleteSaved={(id) => {
              setSaved(saveSavedPresets(saved.filter((entry) => entry.id !== id)));
              setChoice((c) => (c.presetId === id ? { ...c, presetId: null, custom: c.config } : c));
            }}
          />
        )}
        {view.kind === "graph" && (
          <GradeGraph disciplines={config.disciplines} classSize={config.class_size} />
        )}
        {view.kind === "playground" && (
          <Playground
            config={config}
            draft={playground ?? createPlaygroundDraft(config)}
            setDraft={setPlayground}
          />
        )}
        {current && (
          <Comparison
            key={current.id}
            run={current}
            onReuseConfig={() => reuseConfig(current)}
            onRecut={(cuts) => handleRecut(current, cuts)}
            recutting={running}
          />
        )}
      </main>
    </div>
  );
}
