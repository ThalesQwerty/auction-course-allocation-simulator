import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ComparisonOut } from "../types";

interface Props {
  result: ComparisonOut;
}

const AUCTION_COLOR = "#2f6fed";
const CR_COLOR = "#e0913a";

function MetricCard({ label, auction, cr, format }: { label: string; auction: number; cr: number; format?: (n: number) => string }) {
  const fmt = format ?? ((n: number) => n.toFixed(3));
  return (
    <div className="metric-card">
      <div className="label">{label}</div>
      <div className="value">
        <span style={{ color: AUCTION_COLOR }}>{fmt(auction)}</span>
        {" / "}
        <span style={{ color: CR_COLOR }}>{fmt(cr)}</span>
      </div>
      <div style={{ fontSize: 11, color: "var(--muted)" }}>
        <span className="legend-dot" style={{ background: AUCTION_COLOR }} />
        leilão &nbsp;
        <span className="legend-dot" style={{ background: CR_COLOR }} />
        CR (linha de base)
      </div>
    </div>
  );
}

export default function ResultsPanel({ result }: Props) {
  const { auction_metrics: am, cr_metrics: cm } = result;

  const agentIds = Array.from(
    new Set([...Object.keys(am.satisfaction_by_agent), ...Object.keys(cm.satisfaction_by_agent)])
  ).sort();

  const satisfactionData = agentIds.map((id) => ({
    agente: id,
    leilão: am.satisfaction_by_agent[id] ?? 0,
    CR: cm.satisfaction_by_agent[id] ?? 0,
  }));

  return (
    <div className="panel">
      <h2>Resultados: leilão por créditos vs. linha de base por CR</h2>

      <div className="metrics-grid">
        <MetricCard label="Satisfação média (eficiência) — eq. 53" auction={am.average_satisfaction} cr={cm.average_satisfaction} />
        <MetricCard label="Ocupação das vagas — eq. 54" auction={am.occupation_rate} cr={cm.occupation_rate} />
        <MetricCard label="Equidade de Jain — eq. 55" auction={am.fairness_index} cr={cm.fairness_index} />
        <MetricCard label="Correlação c/ CR (Pearson) — eq. 57" auction={am.academic_correlation} cr={cm.academic_correlation} />
      </div>

      <h3 style={{ fontSize: 13, color: "var(--muted)", marginTop: 24 }}>Satisfação por aluno (ψ_a)</h3>
      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer>
          <BarChart data={satisfactionData}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis dataKey="agente" tick={{ fontSize: 12 }} />
            <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="leilão" fill={AUCTION_COLOR} radius={[3, 3, 0, 0]} />
            <Bar dataKey="CR" fill={CR_COLOR} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
