import { useEffect, useState } from "react";
import { compare } from "./api";
import { Comparison } from "./Comparison";
import { Config } from "./Config";
import { choosePreset, editConfig, initialChoice, PresetChoice } from "./presets";
import {
  formatRunDate,
  HistoryEntry,
  loadHistory,
  MAX_RUNS,
  newComparison,
  saveHistory,
} from "./history";
import { GradeGraph } from "./GradeGraph";
import { createPlaygroundDraft, Playground, PlaygroundDraft } from "./Playground";
import { Project } from "./Project";
import { Sidebar, View } from "./Sidebar";

export default function App() {
  const [choice, setChoice] = useState<PresetChoice>(initialChoice);
  const config = choice.config;
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory);
  const [view, setView] = useState<View>({ kind: "config" });
  const [playground, setPlayground] = useState<PlaygroundDraft | null>(null);
  // O modo e o número de execuções não são do cenário: o mesmo cenário se roda
  // uma vez ou se compara N vezes, e trocar de modo não pode mexer nele.
  const [runs, setRuns] = useState(20);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  // O histórico mora no navegador: execuções antigas sobrevivem a um recarregamento.
  useEffect(() => {
    const kept = saveHistory(history);
    if (kept.length !== history.length) setHistory(kept);
  }, [history]);

  function navigate(next: View) {
    setView(next);
    setMenuOpen(false);
  }

  /** Roda a comparação e abre o resultado. A seed do formulário não a
   * acompanha: ali as seeds são as de 1 a N, e o retorno de créditos é o que
   * separa dois dos braços — carregá-los junto guardaria parâmetros que não
   * tiveram efeito nenhum. */
  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const { seed: _seed, credit_return: _return, ...scenario } = config;
      const request = { ...scenario, runs };
      const entry = newComparison(request, await compare(request));
      setHistory((current) => [entry, ...current].slice(0, MAX_RUNS));
      navigate({ kind: "run", id: entry.id });
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
    const { runs: count, ...scenario } = entry.config;
    // Sem seed: ela não fez parte da comparação, então a do formulário fica
    // como está em vez de ser sobrescrita por um valor inventado.
    setChoice((c) => editConfig(c, { ...c.config, ...scenario }));
    setRuns(count);
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
            runs={runs}
            setRuns={setRuns}
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
        {view.kind === "graph" && <GradeGraph disciplines={config.disciplines} />}
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
          />
        )}
      </main>
    </div>
  );
}
