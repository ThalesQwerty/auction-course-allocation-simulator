import { useState } from "react";
import { runAuction } from "./api";
import type { AgentInput, BidInput, GoodInput, RunRequest, RunResponse } from "./types";
import { emptyScenario } from "./types";

/** Renderiza uma variável matemática com subscrito (ex.: W com subscrito a),
 * em vez da notação em texto plano W_a — mais legível na interface. */
function Var({ base, sub }: { base: string; sub: string }) {
  return (
    <>
      {base}
      <sub>{sub}</sub>
    </>
  );
}

function exampleScenario(): RunRequest {
  return {
    agents: [
      { id: "ana", capacity: 8, budget: 100 },
      { id: "bia", capacity: 8, budget: 100 },
      { id: "caio", capacity: 8, budget: 100 },
    ],
    goods: [
      { id: "calc1", quantity: 1, weight: 4 },
      { id: "fis1", quantity: 2, weight: 4 },
    ],
    bids: [
      { agent_id: "ana", good_id: "calc1", credits: 70 },
      { agent_id: "ana", good_id: "fis1", credits: 20 },
      { agent_id: "bia", good_id: "calc1", credits: 55 },
      { agent_id: "bia", good_id: "fis1", credits: 30 },
      { agent_id: "caio", good_id: "fis1", credits: 40 },
    ],
    exclusions: [],
    seed: 42,
  };
}

export default function App() {
  const [scenario, setScenario] = useState<RunRequest>(emptyScenario());
  const [result, setResult] = useState<RunResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateAgent(index: number, patch: Partial<AgentInput>) {
    setScenario((s) => ({ ...s, agents: s.agents.map((a, i) => (i === index ? { ...a, ...patch } : a)) }));
  }
  function updateGood(index: number, patch: Partial<GoodInput>) {
    setScenario((s) => ({ ...s, goods: s.goods.map((g, i) => (i === index ? { ...g, ...patch } : g)) }));
  }
  function updateBid(index: number, patch: Partial<BidInput>) {
    setScenario((s) => ({ ...s, bids: s.bids.map((b, i) => (i === index ? { ...b, ...patch } : b)) }));
  }
  function updateExclusion(index: number, value: string) {
    const goods = value.split(",").map((g) => g.trim()).filter(Boolean);
    setScenario((s) => ({ ...s, exclusions: s.exclusions.map((e, i) => (i === index ? goods : e)) }));
  }

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      setResult(await runAuction(scenario));
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
    } finally {
      setRunning(false);
    }
  }

  function loadExample() {
    setScenario(exampleScenario());
    setResult(null);
    setError(null);
  }

  return (
    <div className="main">
      <h1>Leilão por créditos — simulador</h1>

      {error && <div className="error-banner">{error}</div>}

      <div className="panel">
        <h2>Alunos (agentes)</h2>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>Carga horária máx. (<Var base="W" sub="a" />)</th>
              <th>Orçamento de créditos (<Var base="C" sub="a" />)</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {scenario.agents.map((a, i) => (
              <tr key={i}>
                <td><input value={a.id} onChange={(e) => updateAgent(i, { id: e.target.value })} /></td>
                <td>
                  <input type="number" value={a.capacity} onChange={(e) => updateAgent(i, { capacity: Number(e.target.value) })} />
                </td>
                <td>
                  <input type="number" value={a.budget} onChange={(e) => updateAgent(i, { budget: Number(e.target.value) })} />
                </td>
                <td>
                  <button className="danger" onClick={() => setScenario((s) => ({ ...s, agents: s.agents.filter((_, j) => j !== i) }))}>
                    remover
                  </button>
                </td>
              </tr>
            ))}
            {scenario.agents.length === 0 && (
              <tr><td colSpan={4} className="empty-state">Nenhum aluno ainda.</td></tr>
            )}
          </tbody>
        </table>
        <div className="actions">
          <button className="secondary" onClick={() => setScenario((s) => ({ ...s, agents: [...s.agents, { id: "", capacity: 20, budget: 100 }] }))}>
            + adicionar aluno
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>Disciplinas (bens)</h2>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>Vagas (<Var base="q" sub="x" />)</th>
              <th>Carga horária (<Var base="w" sub="x" />)</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {scenario.goods.map((g, i) => (
              <tr key={i}>
                <td><input value={g.id} onChange={(e) => updateGood(i, { id: e.target.value })} /></td>
                <td>
                  <input type="number" value={g.quantity} onChange={(e) => updateGood(i, { quantity: Number(e.target.value) })} />
                </td>
                <td>
                  <input type="number" value={g.weight} onChange={(e) => updateGood(i, { weight: Number(e.target.value) })} />
                </td>
                <td>
                  <button className="danger" onClick={() => setScenario((s) => ({ ...s, goods: s.goods.filter((_, j) => j !== i) }))}>
                    remover
                  </button>
                </td>
              </tr>
            ))}
            {scenario.goods.length === 0 && (
              <tr><td colSpan={4} className="empty-state">Nenhuma disciplina ainda.</td></tr>
            )}
          </tbody>
        </table>
        <div className="actions">
          <button className="secondary" onClick={() => setScenario((s) => ({ ...s, goods: [...s.goods, { id: "", quantity: 1, weight: 4 }] }))}>
            + adicionar disciplina
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>Lances (créditos apostados por disciplina)</h2>
        <table>
          <thead>
            <tr>
              <th>Aluno</th>
              <th>Disciplina</th>
              <th>Créditos</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {scenario.bids.map((b, i) => (
              <tr key={i}>
                <td>
                  <select value={b.agent_id} onChange={(e) => updateBid(i, { agent_id: e.target.value })}>
                    <option value="" disabled>escolha...</option>
                    {scenario.agents.map((a) => <option key={a.id} value={a.id}>{a.id}</option>)}
                  </select>
                </td>
                <td>
                  <select value={b.good_id} onChange={(e) => updateBid(i, { good_id: e.target.value })}>
                    <option value="" disabled>escolha...</option>
                    {scenario.goods.map((g) => <option key={g.id} value={g.id}>{g.id}</option>)}
                  </select>
                </td>
                <td>
                  <input type="number" min={1} value={b.credits} onChange={(e) => updateBid(i, { credits: Number(e.target.value) })} />
                </td>
                <td>
                  <button className="danger" onClick={() => setScenario((s) => ({ ...s, bids: s.bids.filter((_, j) => j !== i) }))}>
                    remover
                  </button>
                </td>
              </tr>
            ))}
            {scenario.bids.length === 0 && (
              <tr><td colSpan={4} className="empty-state">Nenhum lance ainda.</td></tr>
            )}
          </tbody>
        </table>
        <div className="actions">
          <button
            className="secondary"
            disabled={scenario.agents.length === 0 || scenario.goods.length === 0}
            onClick={() =>
              setScenario((s) => ({
                ...s,
                bids: [...s.bids, { agent_id: s.agents[0]?.id ?? "", good_id: s.goods[0]?.id ?? "", credits: 1 }],
              }))
            }
          >
            + adicionar lance
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>Choque de horário (opcional)</h2>
        <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 0 }}>
          Cada linha é um grupo de disciplinas que um mesmo aluno não pode cursar simultaneamente. Ids separados por
          vírgula (ex.: <code>calc1, fis1</code>).
        </p>
        {scenario.exclusions.map((clique, i) => (
          <div className="field-row" key={i}>
            <input value={clique.join(", ")} onChange={(e) => updateExclusion(i, e.target.value)} />
            <button className="danger" onClick={() => setScenario((s) => ({ ...s, exclusions: s.exclusions.filter((_, j) => j !== i) }))}>
              remover
            </button>
          </div>
        ))}
        <button className="secondary" onClick={() => setScenario((s) => ({ ...s, exclusions: [...s.exclusions, []] }))}>
          + adicionar grupo de exclusão
        </button>
      </div>

      <div className="panel">
        <h2>Parâmetros</h2>
        <div className="field-row">
          <div className="field">
            <label>Seed (reprodutibilidade)</label>
            <input type="number" value={scenario.seed} onChange={(e) => setScenario((s) => ({ ...s, seed: Number(e.target.value) }))} />
          </div>
        </div>
      </div>

      <div className="actions">
        <button className="primary" disabled={running} onClick={handleRun}>
          {running ? "Executando..." : "Executar leilão"}
        </button>
        <button className="secondary" onClick={loadExample}>
          Carregar exemplo
        </button>
      </div>

      {result && <ResultsPanel scenario={scenario} result={result} />}
    </div>
  );
}

type StatusFilter = "all" | "won" | "lost";

function ResultsPanel({ scenario, result }: { scenario: RunRequest; result: RunResponse }) {
  const [agentFilter, setAgentFilter] = useState("all");
  const [goodFilter, setGoodFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const agentIds = Array.from(new Set(scenario.bids.map((b) => b.agent_id))).sort();
  const goodIds = Array.from(new Set(scenario.bids.map((b) => b.good_id))).sort();

  const filteredBids = scenario.bids.filter((b) => {
    if (agentFilter !== "all" && b.agent_id !== agentFilter) return false;
    if (goodFilter !== "all" && b.good_id !== goodFilter) return false;
    if (statusFilter !== "all") {
      const won = result.allocation[`${b.agent_id}|${b.good_id}`] === 1;
      if (statusFilter === "won" && !won) return false;
      if (statusFilter === "lost" && won) return false;
    }
    return true;
  });

  return (
    <div className="panel">
      <h2>Resultado do leilão</h2>

      <div className="field-row">
        <div className="field">
          <label>Aluno</label>
          <select value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}>
            <option value="all">todos</option>
            {agentIds.map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Disciplina</label>
          <select value={goodFilter} onChange={(e) => setGoodFilter(e.target.value)}>
            <option value="all">todas</option>
            {goodIds.map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Resultado</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}>
            <option value="all">todos</option>
            <option value="won">deferido</option>
            <option value="lost">indeferido</option>
          </select>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th>Aluno</th>
            <th>Disciplina</th>
            <th>Lance</th>
            <th>Resultado</th>
            <th>Pago</th>
          </tr>
        </thead>
        <tbody>
          {filteredBids.map((b, i) => {
            const key = `${b.agent_id}|${b.good_id}`;
            const won = result.allocation[key] === 1;
            const paid = result.consumption[key];
            return (
              <tr key={i}>
                <td>{b.agent_id}</td>
                <td>{b.good_id}</td>
                <td>{b.credits}</td>
                <td className={won ? "status-won" : "status-lost"}>{won ? "DEFERIDO" : "INDEFERIDO"}</td>
                <td>{paid !== undefined ? paid : "—"}</td>
              </tr>
            );
          })}
          {filteredBids.length === 0 && (
            <tr><td colSpan={5} className="empty-state">Nenhum lance corresponde aos filtros.</td></tr>
          )}
        </tbody>
      </table>

      <h2 style={{ marginTop: 20 }}>Preço de mercado por disciplina</h2>
      <table>
        <thead><tr><th>Disciplina</th><th>Preço (2º maior lance)</th></tr></thead>
        <tbody>
          {Object.entries(result.prices).map(([good_id, price]) => (
            <tr key={good_id}><td>{good_id}</td><td>{price}</td></tr>
          ))}
        </tbody>
      </table>

      <h2 style={{ marginTop: 20 }}>Orçamento e carga horária restantes por aluno</h2>
      <table>
        <thead>
          <tr>
            <th>Aluno</th>
            <th>Créditos restantes</th>
            <th>Carga horária restante (<Var base="W" sub="a" />)</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(result.remaining_budget).map(([agent_id, remaining]) => (
            <tr key={agent_id}>
              <td>{agent_id}</td>
              <td>{remaining}</td>
              <td>{result.remaining_capacity[agent_id]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
