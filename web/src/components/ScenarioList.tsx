import type { ScenarioOutput } from "../types";

interface Props {
  scenarios: ScenarioOutput[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreateNew: () => void;
}

export default function ScenarioList({ scenarios, selectedId, onSelect, onCreateNew }: Props) {
  return (
    <aside className="sidebar">
      <h1>Cenários</h1>
      <button className="primary" onClick={onCreateNew}>
        + Novo cenário
      </button>
      <ul className="scenario-list">
        {scenarios.map((s) => (
          <li key={s.id}>
            <button className={s.id === selectedId ? "active" : ""} onClick={() => onSelect(s.id)}>
              {s.name || "(sem nome)"}
            </button>
          </li>
        ))}
        {scenarios.length === 0 && <li className="empty-state">Nenhum cenário salvo ainda.</li>}
      </ul>
    </aside>
  );
}
