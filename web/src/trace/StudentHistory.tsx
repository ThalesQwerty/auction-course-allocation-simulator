import { formatCount, formatRatio } from "../charts";
import { DataTable } from "../tables/DataTable";
import type { Column } from "../tables/DataTable";
import {
  GUARANTEED_ROUND,
  OUTCOMES,
  cohortLabel,
} from "../types";
import type { RequestRow, StudentPeriodRow, StudentTracePayload } from "../types";
import { outcomeOf, roundsWith } from "./outcome";
import type { Outcome } from "./outcome";

/** A utilidade é uma fração que soma 1 na linha do aluno, então ela vive na terceira casa: com duas, as disciplinas de uma grade grande empatam todas */
const formatUtility = (value: number) =>
  value.toLocaleString("pt-BR", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  });

export const Chip = ({ outcome }: { outcome: Outcome }) => (
  <span className={`outcome ${outcome.tone}`}>{outcome.label}</span>
);

interface Line {
  request: RequestRow;
  outcome: Outcome;
}

const settledTone = (outcome: Outcome) =>
  outcome.tone === "approved" || outcome.tone === "failed";

export function StudentHistory({
  payload,
  rounds,
  usesCredits,
  aoVoltar,
}: {
  payload: StudentTracePayload;
  rounds: number;
  usesCredits: boolean;
  aoVoltar: () => void;
}) {
  const student = payload.aluno;

  return (
    <>
      <div className="panel student-head">
        <div>
          <button type="button" className="link" onClick={aoVoltar}>
            ← todos os alunos
          </button>
          <h3>{student.nome}</h3>
          <p className="note">
            {cohortLabel(student.ingresso)} · {student.aluno}
          </p>
        </div>
        <dl className="stat-row">
          <div>
            <dt>Ingresso</dt>
            <dd>{`período ${student.ingresso}`}</dd>
          </div>
          <div>
            <dt>Períodos ativos</dt>
            <dd>{student.periodos}</dd>
          </div>
          <div>
            <dt>CR</dt>
            <dd>{student.cr === null ? "—" : formatRatio(student.cr)}</dd>
          </div>
          <div>
            <dt>Intensidade de demanda</dt>
            <dd>
              {student.intensidade === null
                ? "—"
                : `${Math.round(student.intensidade * 100)}%`}
            </dd>
          </div>
          <div>
            <dt>Horas aprovadas</dt>
            <dd>
              {student.carga_aprovada} / {payload.carga_obrigatoria}
            </dd>
          </div>
          <div>
            <dt>Matrículas</dt>
            <dd>{student.matriculas}</dd>
          </div>
          <div>
            <dt>Aprovações</dt>
            <dd>{student.aprovacoes}</dd>
          </div>
          <div>
            <dt>Satisfação média</dt>
            <dd>
              {student.satisfacao === null ? "—" : formatRatio(student.satisfacao)}
            </dd>
          </div>
          <div>
            <dt>Disponibilidade média</dt>
            <dd>
              {student.disponibilidade === null
                ? "—"
                : `${formatCount(student.disponibilidade)} h`}
            </dd>
          </div>
          <div>
            <dt>Saída</dt>
            <dd>
              {student.saida_periodo === null
                ? student.saida
                : `${student.saida} no período ${student.saida_periodo}`}
            </dd>
          </div>
        </dl>
      </div>

      {payload.periodos.length === 0 ? (
        <div className="panel">
          <p className="empty-state">
            Este aluno não pediu nada em nenhum período medido.
          </p>
        </div>
      ) : (
        payload.periodos.map((record) => (
          <StudentPeriod
            key={record.periodo}
            record={record}
            rounds={rounds}
            usesCredits={usesCredits}
          />
        ))
      )}
    </>
  );
}

function StudentPeriod({
  record,
  rounds,
  usesCredits,
}: {
  record: StudentPeriodRow;
  rounds: number;
  usesCredits: boolean;
}) {
  const won = record.solicitacoes.filter(
    (request) => request.rodada_ganha !== null
  ).length;
  const asked = record.solicitacoes.filter((request) =>
    request.lances.some((credits) => credits > 0)
  ).length;
  const guaranteed = record.solicitacoes.some(
    (request) => request.rodada_ganha === GUARANTEED_ROUND
  );
  const linesOf = (round: number): Line[] =>
    record.solicitacoes.flatMap((request) => {
      const outcome = outcomeOf(request, round);
      return outcome ? [{ request, outcome }] : [];
    });
  const open = roundsWith(rounds, (round) => linesOf(round).length > 0);

  return (
    <article className="panel period-panel">
      <header className="period-summary-row">
        <h3>
          {`Período ${record.periodo}`}
          {guaranteed && <span className="badge">matrícula garantida</span>}
        </h3>
        <span className="period-summary">
          {won} de {asked} pedidos atendidos · {record.carga_obtida} h · ψ{" "}
          {formatRatio(record.satisfacao)} · CR {formatRatio(record.cr)}
          {record.disciplinas_elegiveis
            ? ` · demanda ${record.disciplinas_pedidas}/${record.disciplinas_elegiveis}`
            : ""}
          {usesCredits &&
            ` · créditos ${record.creditos_inicio} − ${record.creditos_gasto} → ${record.creditos_fim}`}
          {usesCredits && ` · retorno γ ${record.creditos_retorno}`}
        </span>
      </header>

      {open.map((round) => {
        const lines = linesOf(round);
        return (
          <div className="round-block" key={round}>
            <h4 className="round-head">
              Rodada {round}
              <span className="round-count">
                {lines.length === 1 ? "1 turma" : `${lines.length} turmas`}
              </span>
            </h4>
            <DataTable
              rows={lines}
              columns={lineColumns(round, usesCredits)}
              chave={(line) => line.request.turma}
              inicial={{
                chave: usesCredits ? "lance" : "utilidade",
                desc: true,
              }}
            />
          </div>
        );
      })}
    </article>
  );
}

function lineColumns(round: number, usesCredits: boolean): Column<Line>[] {
  const bid = (line: Line) => line.request.lances[round - 1] ?? 0;
  const columns: Column<Line>[] = [
    {
      chave: "turma",
      rotulo: "Turma",
      tipo: "texto",
      valor: (line) => line.request.turma,
    },
    {
      chave: "utilidade",
      rotulo: "Utilidade",
      tipo: "numero",
      valor: (line) => line.request.utilidade,
      escreve: (line) => formatUtility(line.request.utilidade),
    },
  ];

  if (usesCredits) {
    columns.push({
      chave: "lance",
      rotulo: "Lance",
      tipo: "numero",
      valor: bid,
      escreve: (line) => bid(line) || "—",
    });
  }

  columns.push(
    {
      chave: "resultado",
      rotulo: "Resultado",
      tipo: "enum",
      ordem: OUTCOMES,
      valor: (line) => line.outcome.label,
      escreve: (line) => (
        <>
          <Chip outcome={line.outcome} />
          {line.outcome.guaranteed && (
            <span className="outcome-note">vaga garantida</span>
          )}
        </>
      ),
    },
    {
      chave: "nota",
      rotulo: "Nota",
      tipo: "numero",
      valor: (line) =>
        settledTone(line.outcome) ? line.request.nota : null,
      escreve: (line) =>
        settledTone(line.outcome) && line.request.nota !== null ? (
          <span className={line.outcome.tone}>
            {formatRatio(line.request.nota)}
            {line.request.tentativa && line.request.tentativa > 1
              ? ` (${line.request.tentativa}ª tentativa)`
              : ""}
          </span>
        ) : (
          "—"
        ),
    }
  );

  if (usesCredits) {
    columns.push(
      {
        chave: "pago",
        rotulo: "Pago",
        tipo: "numero",
        valor: (line) => (settledTone(line.outcome) ? line.request.pago : null),
      },
      {
        chave: "retorno",
        rotulo: "Retorno γ",
        tipo: "numero",
        valor: (line) => (settledTone(line.outcome) ? line.request.retorno : null),
      }
    );
  }

  return columns;
}
