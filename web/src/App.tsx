import { useEffect, useState } from "react";
import { api } from "./api/client";
import ScenarioList from "./components/ScenarioList";
import ScenarioEditor from "./components/ScenarioEditor";
import ResultsPanel from "./components/ResultsPanel";
import { emptyScenario, type ComparisonOut, type ScenarioInput, type ScenarioOutput } from "./types";

export default function App() {
  const [scenarios, setScenarios] = useState<ScenarioOutput[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ScenarioInput>(emptyScenario());
  const [result, setResult] = useState<ComparisonOut | null>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshList() {
    try {
      setScenarios(await api.listScenarios());
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    refreshList();
  }, []);

  function handleCreateNew() {
    setSelectedId(null);
    setDraft(emptyScenario());
    setResult(null);
    setError(null);
  }

  async function handleSelect(id: string) {
    setError(null);
    setResult(null);
    try {
      const scenario = await api.getScenario(id);
      setSelectedId(id);
      setDraft(scenario);
      try {
        setResult(await api.getResult(id));
      } catch {
        setResult(null); // ainda não executado — não é um erro
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleSave(input: ScenarioInput) {
    setSaving(true);
    setError(null);
    try {
      const saved = selectedId ? await api.updateScenario(selectedId, input) : await api.createScenario(input);
      setSelectedId(saved.id);
      setDraft(saved);
      await refreshList();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleRun() {
    if (!selectedId) return;
    setRunning(true);
    setError(null);
    try {
      setResult(await api.runSimulation(selectedId));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="app">
      <ScenarioList
        scenarios={scenarios}
        selectedId={selectedId}
        onSelect={handleSelect}
        onCreateNew={handleCreateNew}
      />
      <main className="main">
        <h1 style={{ fontSize: 20 }}>Leilão por créditos — matrícula universitária</h1>
        {error && <div className="error-banner">{error}</div>}
        <ScenarioEditor
          key={selectedId ?? "new"}
          initial={draft}
          onSave={handleSave}
          onRun={handleRun}
          saving={saving}
          running={running}
          isNew={selectedId === null}
        />
        {result && <ResultsPanel result={result} />}
      </main>
    </div>
  );
}
