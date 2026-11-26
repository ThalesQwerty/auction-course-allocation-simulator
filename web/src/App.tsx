import { useEffect, useState } from "react";
import {
  comparisonResult,
  comparisonState,
  createComparison,
  deleteComparison,
  listComparisons,
  runComparison,
} from "./api";
import { Comparison } from "./Comparison";
import { Config } from "./Config";
import { choosePreset, editConfig, initialChoice, PresetChoice } from "./presets";
import {
  loadSavedPresets,
  saveSavedPresets,
  upsertSavedPreset,
} from "./savedPresets";
import {
  entryFromComparison,
  formatRunDate,
  HistoryEntry,
  runFromComparison,
} from "./history";
import type { ComparisonRun } from "./history";
import { GradeGraph } from "./GradeGraph";
import { createPlaygroundDraft, Playground, PlaygroundDraft } from "./Playground";
import { RunProgress, RunningSimulation } from "./RunProgress";
import { Sidebar, View } from "./Sidebar";
import { COMPARISON_ARMS } from "./types";
import type { ComparisonState } from "./types";

/** De quanto em quanto se pergunta à API como vai a comparação */
const POLL_MS = 5_000;

export default function App() {
  const [choice, setChoice] = useState<PresetChoice>(initialChoice);
  const [saved, setSaved] = useState(loadSavedPresets);
  const config = choice.config;
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [opened, setOpened] = useState<ComparisonRun | null>(null);
  const [view, setView] = useState<View>({ kind: "config" });
  const [playground, setPlayground] = useState<PlaygroundDraft | null>(null);
  const [runs, setRuns] = useState(20);
  const [arms, setArms] = useState<string[]>(() => COMPARISON_ARMS.map((arm) => arm.key));
  const [running, setRunning] = useState(false);
   /** Como vai a comparação em curso: o que a API respondeu na última consulta */
  const [progress, setProgress] = useState<RunProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    refreshHistory().catch((e) => {
      if (alive) setError((e as Error).message);
    });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (view.kind !== "run" || opened?.id === view.id) return;
    const name = view.id;
    let alive = true;
    setOpened(null);
    comparisonResult(name)
      .then((head) => {
        if (alive) setOpened(runFromComparison(head));
      })
      .catch((e) => {
        if (!alive) return;
        setError((e as Error).message);
        navigate({ kind: "config" });
      });
    return () => {
      alive = false;
    };
  }, [view, opened?.id]);

  async function refreshHistory(): Promise<HistoryEntry[]> {
    const listed = (await listComparisons()).map(entryFromComparison);
    setHistory(listed);
    return listed;
  }

  function navigate(next: View) {
    setView(next);
    setMenuOpen(false);
  }

   /** Roda a comparação e **abre o resultado na hora**: o card de andamento é
    * que acompanha, e os gráficos se preenchem quando a fila esvazia */
  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const { seed: _seed, ...scenario } = config;
      const request = { ...scenario, runs, arms };
      const criada = await createComparison(request);
      await refreshHistory();
      await runComparison(criada.nome);
      setProgress({
        name: criada.nome,
        done: 0,
        total: runs * arms.length,
        share: 0,
        startedAt: Date.now(),
        current: null,
      });
      navigate({ kind: "run", id: criada.nome });
      const pronta = await waitFor(criada.nome);
      await refreshHistory();
      if (pronta.falhas && pronta.falhas === pronta.simulacoes.length) {
        throw new Error(
          `as ${pronta.falhas} simulações falharam: ${
            pronta.simulacoes.find((s) => s.erro)?.erro ?? "sem detalhe"
          }`
        );
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
      setProgress(null);
    }
  }

   /** Acompanha até a fila esvaziar. O WAL deixa a API ler enquanto o laço grava */
  async function waitFor(name: string) {
    while (true) {
      const state = await comparisonState(name);
      setProgress((atual) => ({
        name,
        done: state.concluidas + state.falhas + state.estouros,
        total: state.simulacoes.length,
        share: state.etapas_total ? state.etapas / state.etapas_total : null,
        startedAt: atual?.startedAt ?? Date.now(),
        current: simulationNow(state),
      }));
      if (state.pendentes + state.rodando === 0) return state;
      if (state.estado === "falhou") {
        throw new Error(state.erro ?? "a comparação falhou");
      }
      await new Promise((wake) => setTimeout(wake, POLL_MS));
    }
  }

   /** A simulação em curso. Com um worker é uma só; com vários, a primeira delas */
  function simulationNow(state: ComparisonState): RunningSimulation | null {
    const now = state.simulacoes.find((s) => s.estado === "rodando");
    if (!now || !state.etapas_total) return null;
    const ceiling = state.etapas_total / state.simulacoes.length;
    return {
      arm: now.braco,
      seed: now.seed,
      seeds: state.seeds,
      share: ceiling ? Math.min(1, now.etapas / ceiling) : 0,
    };
  }

  async function handleDelete(id: string) {
    const entry = history.find((e) => e.id === id);
    if (!entry) return;
    if (
      !confirm(
        `Apagar a execução de ${formatRunDate(entry.at)}? Ela sai do disco, e a ação não pode ser desfeita.`
      )
    )
      return;
    await discard([id]);
  }

  async function handleClear() {
    if (
      !confirm(
        "Apagar todas as execuções? Elas saem do disco, e a ação não pode ser desfeita."
      )
    )
      return;
    await discard(history.map((entry) => entry.id));
  }

   /** Apaga do disco e refaz a lista. Uma falha não impede as demais */
  async function discard(names: string[]) {
    setError(null);
    const done = await Promise.allSettled(names.map(deleteComparison));
    const failed = done.filter((entry) => entry.status === "rejected");
    if (failed.length) {
      setError(
        `${failed.length} de ${names.length} não foram apagadas: ${
          (failed[0] as PromiseRejectedResult).reason?.message
        }`
      );
    }
    await refreshHistory().catch((e) => setError((e as Error).message));
    if (view.kind === "run" && names.includes(view.id)) {
      setOpened(null);
      navigate({ kind: "config" });
    }
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


  const current = view.kind === "run" && opened?.id === view.id ? opened : undefined;
  const showConfig = view.kind === "config";

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
      />

      <main className="main wide">
        {error && (
          <div className="error-banner" role="alert">
            {error}
            <button type="button" className="ghost" onClick={() => setError(null)}>
              Fechar
            </button>
          </div>
        )}
        {showConfig && (
          <Config
            config={config}
            setConfig={(update) => setChoice((c) => editConfig(c, update(c.config)))}
            runs={runs}
            setRuns={setRuns}
            arms={arms}
            setArms={setArms}
            running={running}
            progress={progress}
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
        {view.kind === "run" && !current && (
          <p className="loading">Carregando…</p>
        )}
        {current && (
          <Comparison
            key={`${current.id}-${progress?.name === current.id ? "rodando" : "pronta"}`}
            run={current}
            progress={progress?.name === current.id ? progress : null}
            onReuseConfig={() => reuseConfig(current)}
          />
        )}
      </main>
    </div>
  );
}
