import { useState, useEffect } from "react";
import type { ScenarioAgent, ScenarioDemand, ScenarioGood, ScenarioInput } from "../types";

interface Props {
  initial: ScenarioInput;
  onSave: (input: ScenarioInput) => Promise<void>;
  onRun: () => Promise<void>;
  saving: boolean;
  running: boolean;
  isNew: boolean;
}

function emptyAgent(): ScenarioAgent {
  return { id: "", capacity: 20, budget: 100, academic_index: 5 };
}
function emptyGood(): ScenarioGood {
  return { id: "", quantity: 1, weight: 4 };
}
function emptyDemand(agents: ScenarioAgent[], goods: ScenarioGood[]): ScenarioDemand {
  return { agent_id: agents[0]?.id ?? "", good_id: goods[0]?.id ?? "", utility: 0.5 };
}

export default function ScenarioEditor({ initial, onSave, onRun, saving, running, isNew }: Props) {
  const [draft, setDraft] = useState<ScenarioInput>(initial);

  useEffect(() => setDraft(initial), [initial]);

  function updateAgent(index: number, patch: Partial<ScenarioAgent>) {
    setDraft((d) => ({
      ...d,
      agents: d.agents.map((a, i) => (i === index ? { ...a, ...patch } : a)),
    }));
  }
  function updateGood(index: number, patch: Partial<ScenarioGood>) {
    setDraft((d) => ({
      ...d,
      goods: d.goods.map((g, i) => (i === index ? { ...g, ...patch } : g)),
    }));
  }
  function updateDemand(index: number, patch: Partial<ScenarioDemand>) {
    setDraft((d) => ({
      ...d,
      demands: d.demands.map((dem, i) => (i === index ? { ...dem, ...patch } : dem)),
    }));
  }
  function updateExclusion(index: number, value: string) {
    const goods = value
      .split(",")
      .map((g) => g.trim())
      .filter(Boolean);
    setDraft((d) => ({ ...d, exclusions: d.exclusions.map((e, i) => (i === index ? goods : e)) }));
  }

  return (
    <div>
      <div className="panel">
        <h2>Cenário</h2>
        <div className="field-row">
          <div className="field" style={{ flex: 1 }}>
            <label>Nome</label>
            <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          </div>
          <div className="field">
            <label>Rodadas de alocação</label>
            <input
              type="number"
              min={1}
              value={draft.num_rounds}
              onChange={(e) => setDraft({ ...draft, num_rounds: Number(e.target.value) })}
            />
          </div>
          <div className="field">
            <label>Seed (reprodutibilidade)</label>
            <input
              type="number"
              value={draft.seed}
              onChange={(e) => setDraft({ ...draft, seed: Number(e.target.value) })}
            />
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Alunos (agentes A)</h2>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>Carga horária máx. (W_a)</th>
              <th>Orçamento de créditos (C_a)</th>
              <th>CR (N_a)</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {draft.agents.map((a, i) => (
              <tr key={i}>
                <td>
                  <input value={a.id} onChange={(e) => updateAgent(i, { id: e.target.value })} />
                </td>
                <td>
                  <input
                    type="number"
                    value={a.capacity}
                    onChange={(e) => updateAgent(i, { capacity: Number(e.target.value) })}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    value={a.budget}
                    onChange={(e) => updateAgent(i, { budget: Number(e.target.value) })}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    step="0.1"
                    value={a.academic_index}
                    onChange={(e) => updateAgent(i, { academic_index: Number(e.target.value) })}
                  />
                </td>
                <td>
                  <button
                    className="danger"
                    onClick={() => setDraft((d) => ({ ...d, agents: d.agents.filter((_, j) => j !== i) }))}
                  >
                    remover
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p />
        <button className="secondary" onClick={() => setDraft((d) => ({ ...d, agents: [...d.agents, emptyAgent()] }))}>
          + adicionar aluno
        </button>
      </div>

      <div className="panel">
        <h2>Disciplinas (bens B)</h2>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>Vagas (q_x)</th>
              <th>Carga horária (w_x)</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {draft.goods.map((g, i) => (
              <tr key={i}>
                <td>
                  <input value={g.id} onChange={(e) => updateGood(i, { id: e.target.value })} />
                </td>
                <td>
                  <input
                    type="number"
                    value={g.quantity}
                    onChange={(e) => updateGood(i, { quantity: Number(e.target.value) })}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    value={g.weight}
                    onChange={(e) => updateGood(i, { weight: Number(e.target.value) })}
                  />
                </td>
                <td>
                  <button
                    className="danger"
                    onClick={() => setDraft((d) => ({ ...d, goods: d.goods.filter((_, j) => j !== i) }))}
                  >
                    remover
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p />
        <button className="secondary" onClick={() => setDraft((d) => ({ ...d, goods: [...d.goods, emptyGood()] }))}>
          + adicionar disciplina
        </button>
      </div>

      <div className="panel">
        <h2>Solicitações (demandas D) e utilidade percebida</h2>
        <table>
          <thead>
            <tr>
              <th>Aluno</th>
              <th>Disciplina</th>
              <th>Utilidade percebida (u_a,x, 0–1)</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {draft.demands.map((dem, i) => (
              <tr key={i}>
                <td>
                  <select value={dem.agent_id} onChange={(e) => updateDemand(i, { agent_id: e.target.value })}>
                    {draft.agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.id}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select value={dem.good_id} onChange={(e) => updateDemand(i, { good_id: e.target.value })}>
                    {draft.goods.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.id}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    type="number"
                    min={0.01}
                    max={1}
                    step="0.05"
                    value={dem.utility}
                    onChange={(e) => updateDemand(i, { utility: Number(e.target.value) })}
                  />
                </td>
                <td>
                  <button
                    className="danger"
                    onClick={() => setDraft((d) => ({ ...d, demands: d.demands.filter((_, j) => j !== i) }))}
                  >
                    remover
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p />
        <button
          className="secondary"
          disabled={draft.agents.length === 0 || draft.goods.length === 0}
          onClick={() => setDraft((d) => ({ ...d, demands: [...d.demands, emptyDemand(d.agents, d.goods)] }))}
        >
          + adicionar solicitação
        </button>
      </div>

      <div className="panel">
        <h2>Choque de horário (exclusões mútuas X)</h2>
        <p style={{ fontSize: 13, color: "var(--muted)" }}>
          Cada linha é um clique: disciplinas que um mesmo aluno não pode cursar simultaneamente. Liste os ids
          separados por vírgula (ex.: <code>x1, x2, x3</code>).
        </p>
        {draft.exclusions.map((clique, i) => (
          <div key={i} className="row-actions" style={{ marginBottom: 8 }}>
            <input value={clique.join(", ")} onChange={(e) => updateExclusion(i, e.target.value)} />
            <button
              className="danger"
              onClick={() => setDraft((d) => ({ ...d, exclusions: d.exclusions.filter((_, j) => j !== i) }))}
            >
              remover
            </button>
          </div>
        ))}
        <button className="secondary" onClick={() => setDraft((d) => ({ ...d, exclusions: [...d.exclusions, []] }))}>
          + adicionar clique de exclusão
        </button>
      </div>

      <div className="row-actions">
        <button className="primary" disabled={saving} onClick={() => onSave(draft)}>
          {saving ? "Salvando..." : isNew ? "Criar cenário" : "Salvar alterações"}
        </button>
        <button className="secondary" disabled={running || isNew} onClick={onRun}>
          {running ? "Executando..." : "Executar simulação"}
        </button>
      </div>
    </div>
  );
}
