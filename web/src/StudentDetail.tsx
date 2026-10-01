import { useMemo } from "react";
import { MetricChart, SeriesPoint, courseColors, formatCount, formatRatio, usePrefersDark } from "./charts";
import type { RequestRecord, StudentHistory, StudentPeriodRecord, StudentSummary } from "./types";

const KIND_LABEL: Record<RequestRecord["kind"], string> = {
  required: "obrigatória",
  elective: "optativa",
  free: "livre",
};

/** As três saídas possíveis de um pedido. "sem lance" é a que mais explica
 * resultado inesperado: a disciplina saiu de B_a^(t,r) antes do leilão. */
function outcome(request: RequestRecord): { label: string; className: string } {
  if (request.won_round !== null) return { label: `atendida (rodada ${request.won_round})`, className: "won" };
  if (request.bids.some((credits) => credits > 0)) return { label: "recusada", className: "refused" };
  return { label: "sem lance", className: "unbid" };
}

/** Uma série por grandeza, com o período no eixo horizontal. Diferente dos
 * gráficos agregados (uma linha por curso), aqui a linha é a do próprio aluno:
 * esta tela existe para investigar um caso individual. */
function series(records: StudentPeriodRecord[], values: (r: StudentPeriodRecord) => Record<string, number>): SeriesPoint[] {
  return records.map((record) => ({ x: String(record.period), ...values(record) }));
}

export function StudentDetail({
  student,
  history,
  courseColor,
}: {
  student: StudentSummary;
  history: StudentHistory;
  courseColor: string;
}) {
  const dark = usePrefersDark();
  const records = history.periods;

  const charts = useMemo(() => {
    const keys = ["aprovadas", "meta", "CR", "satisfação", "no início", "gastos", "retorno", "no fim", "solicitadas", "atendidas", "aprovadas no período"];
    const colors = courseColors(keys, dark);
    return { colors };
  }, [dark]);

  if (records.length === 0) {
    return (
      <>
        <Header student={student} courseColor={courseColor} />
        <div className="panel">
          <p className="empty-state">
            Este aluno não participou de nenhum período: ingressou no período {student.entry_period},
            depois do fim do cenário, ou todas as disciplinas elegíveis já estavam aprovadas.
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <Header student={student} courseColor={courseColor} />

      <div className="chart-grid">
        <MetricChart
          title="Progressão curricular"
          hint={`Carga horária aprovada contra a meta do curso (${student.hours_to_graduate} h) — eq. (39)`}
          data={series(records, (r) => ({ aprovadas: r.approved_hours, meta: student.hours_to_graduate }))}
          courses={["aprovadas", "meta"]}
          colors={charts.colors}
          domain={[0, "auto"]}
          format={formatCount}
        />
        <MetricChart
          title="Coeficiente de rendimento"
          hint="N_a no início de cada período — eq. (49)"
          data={series(records, (r) => ({ CR: r.grade_average }))}
          courses={["CR"]}
          colors={charts.colors}
          domain={[0, 10]}
        />
        <MetricChart
          title="Satisfação (ψ)"
          hint="Fração da utilidade desejada que o aluno obteve — eq. (51)"
          data={series(records, (r) => ({ satisfação: r.satisfaction }))}
          courses={["satisfação"]}
          colors={charts.colors}
          domain={[0, 1]}
        />
        <MetricChart
          title="Créditos"
          hint="Orçamento no início, consumo no leilão, retorno das disciplinas e saldo carregado — eqs. (27), (34) e (36)"
          data={series(records, (r) => ({
            "no início": r.credits_start,
            gastos: r.credits_spent,
            retorno: r.credits_returned,
            "no fim": r.credits_end,
          }))}
          courses={["no início", "gastos", "retorno", "no fim"]}
          colors={charts.colors}
          domain={[0, "auto"]}
          format={formatCount}
        />
        <MetricChart
          title="Disciplinas por período"
          hint="Quantas pediu, quantas conseguiu e em quantas foi aprovado"
          data={series(records, (r) => ({
            solicitadas: r.requests.filter((q) => q.bids.some((c) => c > 0)).length,
            atendidas: r.requests.filter((q) => q.won_round !== null).length,
            "aprovadas no período": r.requests.filter((q) => q.approved).length,
          }))}
          courses={["solicitadas", "atendidas", "aprovadas no período"]}
          colors={charts.colors}
          domain={[0, "auto"]}
          format={formatCount}
        />
      </div>

      {records.map((record) => (
        <PeriodPanel key={record.period} record={record} />
      ))}
    </>
  );
}

function Header({ student, courseColor }: { student: StudentSummary; courseColor: string }) {
  return (
    <div className="panel student-head">
      <div>
        <h1>{student.name}</h1>
        <p className="note">
          <span className="swatch" style={{ background: courseColor }} /> {student.course} · {student.id}
        </p>
      </div>
      <dl className="stat-row">
        <div>
          <dt>Ingresso</dt>
          <dd>{`período ${student.entry_period}`}</dd>
        </div>
        <div>
          <dt>CR</dt>
          <dd>{formatRatio(student.grade_average)}</dd>
        </div>
        <div>
          <dt>Horas aprovadas</dt>
          <dd>
            {student.approved_hours} / {student.hours_to_graduate}
          </dd>
        </div>
        <div>
          <dt>Créditos</dt>
          <dd>{student.credits}</dd>
        </div>
        <div>
          <dt>Matrículas</dt>
          <dd>{student.enrollments}</dd>
        </div>
        <div>
          <dt>Aprovações</dt>
          <dd>{student.approvals}</dd>
        </div>
        <div>
          <dt>Satisfação média</dt>
          <dd>{formatRatio(student.mean_satisfaction)}</dd>
        </div>
        <div>
          <dt>Saída</dt>
          <dd>
            {student.graduated_at
              ? `formado no período ${student.graduated_at}`
              : student.dismissed_at
                ? `jubilado no período ${student.dismissed_at}`
                : "—"}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function PeriodPanel({ record }: { record: StudentPeriodRecord }) {
  const won = record.requests.filter((q) => q.won_round !== null).length;
  const asked = record.requests.filter((q) => q.bids.some((c) => c > 0)).length;
  const rounds = record.requests[0]?.bids.length ?? 1;

  return (
    <details className="panel period-panel" open>
      <summary>
        <div className="period-summary-row">
          <h2>
            {`Período ${record.period}`}
            {record.graduated && <span className="badge">concluiu o curso</span>}
            {record.dismissed && <span className="badge">jubilado por decurso de prazo</span>}
          </h2>
          <span className="period-summary">
            {won} de {asked} pedidos atendidos · {record.enrolled_hours} h · ψ{" "}
            {formatRatio(record.satisfaction)} · CR {formatRatio(record.grade_average)} · créditos{" "}
            {record.credits_start} − {record.credits_spent} → {record.credits_end}
            {record.credits_returned > 0 && ` · retorno γ ${record.credits_returned}`}
          </span>
        </div>
      </summary>

      <table>
        <thead>
          <tr>
            <th>Disciplina</th>
            <th>Grade</th>
            <th>Utilidade</th>
            <th>{rounds > 1 ? `Lances (${rounds} rodadas)` : "Lance"}</th>
            <th>Resultado</th>
            <th>Pago</th>
            <th>Tentativa</th>
            <th>Nota</th>
            <th>Retorno</th>
          </tr>
        </thead>
        <tbody>
          {record.requests.map((request) => {
            const status = outcome(request);
            return (
              <tr key={request.discipline}>
                <td>{request.discipline}</td>
                <td className="muted-cell">{KIND_LABEL[request.kind]}</td>
                <td>{request.utility.toLocaleString("pt-BR", { maximumFractionDigits: 3 })}</td>
                <td className="muted-cell">{request.bids.map((c) => c || "—").join(" / ")}</td>
                <td className={`outcome ${status.className}`}>{status.label}</td>
                <td>{request.paid || "—"}</td>
                <td>{request.attempt ?? "—"}</td>
                <td className={request.grade === null ? undefined : request.approved ? "approved" : "failed"}>
                  {request.grade === null ? "—" : formatRatio(request.grade)}
                </td>
                {/* Traço só para quem não cursou: num pedido atendido o zero é
                    informação (a política não devolveu nada por ele). */}
                <td>{request.attempt === null ? "—" : request.returned}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </details>
  );
}
