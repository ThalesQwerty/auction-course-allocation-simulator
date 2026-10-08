import { useEffect, useState } from "react";
import { compare, simulate } from "./api";
import type { SweepIn } from "./types";
import { Comparison } from "./Comparison";
import { Config, RunMode } from "./Config";
import { choosePreset, editConfig, initialChoice, PresetChoice } from "./presets";
import {
  formatRunDate,
  HistoryEntry,
  loadHistory,
  MAX_RUNS,
  newComparison,
  newRun,
  saveHistory,
  SimulationRun,
} from "./history";
import { Project } from "./Project";
import { Results } from "./Results";
import { Sidebar, View } from "./Sidebar";

export default function App() {
  const [choice, setChoice] = useState<PresetChoice>(initialChoice);
  const config = choice.config;
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory);
  const [view, setView] = useState<View>({ kind: "config" });
  // O modo e o número de execuções não são do cenário: o mesmo cenário se roda
  // uma vez ou se compara N vezes, e trocar de modo não pode mexer nele.
  const [mode, setMode] = useState<RunMode>("single");
  const [runs, setRuns] = useState(20);
  const [sweep, setSweep] = useState<SweepIn | null>(null);
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

  /** Executa o que o modo pede e abre o resultado. Os dois caminhos só diferem
   * no que mandam para o servidor e no que guardam; a seed do formulário não
   * acompanha a comparação, que usa as suas próprias (1..N). */
  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      let entry: HistoryEntry;
      if (mode === "compare") {
        // Nem a seed nem o retorno de créditos acompanham a comparação: ali
        // as seeds são as de 1 a N, e o retorno é o que separa dois dos três
        // modelos. Carregá-los junto guardaria parâmetros que não tiveram
        // efeito nenhum no resultado.
        const { seed: _seed, credit_return: _return, ...scenario } = config;
        const request = { ...scenario, runs, ...(sweep ? { sweep } : {}) };
        entry = newComparison(request, await compare(request));
      } else {
        entry = newRun(config, await simulate(config));
      }
      setHistory((current) => [entry, ...current].slice(0, MAX_RUNS));
      navigate({ kind: "run", id: entry.id });
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
      setHistory((current) =>
        current.map((entry) =>
          entry.id === run.id && entry.kind === "simulation" ? { ...entry, result } : entry
        )
      );
    } catch (e) {
      setHistoriesError((e as Error).message);
    } finally {
      setLoadingHistories(false);
    }
  }

  function handleDelete(id: string) {
    const entry = history.find((e) => e.id === id);
    if (!entry) return;
    if (!confirm(`Apagar a execução de ${formatRunDate(entry.at)}? A ação não pode ser desfeita.`))
      return;
    setHistory((current) => current.filter((e) => e.id !== id));
    // Se a execução apagada era a que estava na tela, volta para a configuração.
    if (view.kind === "run" && view.id === id) navigate({ kind: "config" });
  }

  function handleClear() {
    if (!confirm("Apagar todas as execuções guardadas? A ação não pode ser desfeita.")) return;
    setHistory([]);
    navigate({ kind: "config" });
  }

  /** Volta ao formulário com o cenário de uma execução carregado. Uma
   * comparação devolve também o N e o modo, senão "reabrir" daria um
   * formulário que não reproduz o que está na tela. */
  function reuseConfig(entry: HistoryEntry) {
    if (entry.kind === "comparison") {
      const { runs: count, ...scenario } = entry.config;
      // Sem seed: ela não fez parte da comparação, então a do formulário fica
      // como está em vez de ser sobrescrita por um valor inventado.
      setChoice((c) => editConfig(c, { ...c.config, ...scenario }));
      setRuns(count);
      setMode("compare");
    } else {
      setChoice((c) => editConfig(c, entry.config));
      setMode("single");
    }
    setError(null);
    navigate({ kind: "config" });
  }

  // Uma execução apagada pelo limite de espaço cai de volta na configuração
  // em vez de deixar a tela em branco.
  const current = view.kind === "run" ? history.find((entry) => entry.id === view.id) : undefined;
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
            mode={mode}
            setMode={setMode}
            runs={runs}
            setRuns={setRuns}
            sweep={sweep}
            setSweep={setSweep}
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
        {current?.kind === "comparison" && (
          <Comparison
            key={current.id}
            run={current}
            onReuseConfig={() => reuseConfig(current)}
          />
        )}
        {current?.kind === "simulation" && (
          <Results
            key={current.id}
            run={current}
            onReuseConfig={() => reuseConfig(current)}
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
