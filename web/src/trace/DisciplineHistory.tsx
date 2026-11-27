import { formatRatio } from "../charts";
import { DataTable } from "../tables/DataTable";
import type { Column } from "../tables/DataTable";
import { OUTCOMES } from "../types";
import type {
  ClassPeriodRow,
  DisciplineBidRow,
  DisciplinePeriodRow,
  DisciplineTracePayload,
} from "../types";
import { Chip } from "./StudentHistory";
import { outcomeOf, roundsWith } from "./outcome";
import type { Outcome } from "./outcome";

const formatUtility = (value: number) =>
  value.toLocaleString("pt-BR", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  });

const number = (value: number | null) =>
  value === null ? "—" : formatRatio(value);

interface Line {
  request: DisciplineBidRow;
  outcome: Outcome;
}

const settledTone = (outcome: Outcome) =>
  outcome.tone === "approved" || outcome.tone === "failed";

export function DisciplineHistory({
  payload,
  rounds,
  usesCredits,
  aoVoltar,
}: {
  payload: DisciplineTracePayload;
  rounds: number;
  usesCredits: boolean;
  aoVoltar: () => void;
}) {
  const head = payload.disciplina;

  return (
    <>
      <div className="panel student-head">
        <div>
          <button type="button" className="link" onClick={aoVoltar}>
            ← todas as disciplinas
          </button>
          <h3>{head.disciplina}</h3>
          <p className="note">
            {head.carga} h ·{" "}
            {head.optativa ? "optativa" : `período ${head.nivel} da grade`} ·{" "}
            {head.turmas === 1 ? "1 turma" : `${head.turmas} turmas`} · {head.vagas}{" "}
            vagas
          </p>
          <p className="trace-profiles">
            {payload.turmas.map((turma) => (
              <span className="chip" key={turma.turma}>
                {turma.turma} · {turma.horario} · {turma.vagas} vagas
              </span>
            ))}
          </p>
        </div>
      </div>

      {payload.periodos.length === 0 ? (
        <div className="panel">
          <p className="empty-state">
            Nenhum aluno medido pediu esta disciplina em período algum.
          </p>
        </div>
      ) : (
        payload.periodos.map((period) => (
          <DisciplinePeriod
            key={period.periodo}
            period={period}
            rounds={rounds}
            usesCredits={usesCredits}
          />
        ))
      )}
    </>
  );
}

function DisciplinePeriod({
  period,
  rounds,
  usesCredits,
}: {
  period: DisciplinePeriodRow;
  rounds: number;
  usesCredits: boolean;
}) {
  const linesOf = (round: number): Line[] =>
    period.solicitacoes
      .flatMap((request) => {
        const outcome = outcomeOf(request, round);
        return outcome ? [{ request, outcome }] : [];
      })
      .filter(
        ({ request, outcome }) =>
          (request.lances[round - 1] ?? 0) > 0 || settledTone(outcome)
      );
  const open = roundsWith(rounds, (round) => linesOf(round).length > 0);

  return (
    <article className="panel period-panel">
      <header className="period-summary-row">
        <h3>{`Período ${period.periodo}`}</h3>
        <span className="period-summary">
          {period.resumo.preenchidas} de {period.resumo.vagas} vagas preenchidas
          {period.resumo.concedidas > 0 &&
            ` (${period.resumo.concedidas} em rodada)`}{" "}
          · {period.resumo.pedidos} solicitantes · {period.resumo.aprovacoes}{" "}
          aprovações · {period.resumo.exclusoes} exclusões
        </span>
      </header>

      <div className="round-block">
        <h4 className="round-head">
          Turmas
          <span className="round-count">
            {period.turmas.length === 1
              ? "1 turma"
              : `${period.turmas.length} turmas`}
          </span>
        </h4>
        <DataTable
          rows={period.turmas}
          columns={classColumns(usesCredits)}
          chave={(turma) => turma.turma}
          inicial={{ chave: "pedidos", desc: true }}
        />
      </div>

      {open.map((round) => {
        const lines = linesOf(round);
        return (
          <div className="round-block" key={round}>
            <h4 className="round-head">
              Rodada {round}
              <span className="round-count">
                {lines.length === 1 ? "1 pedido" : `${lines.length} pedidos`}
              </span>
            </h4>
            <DataTable
              rows={lines}
              columns={bidColumns(round, usesCredits)}
              chave={(line) => `${line.request.aluno}·${line.request.turma}`}
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

function classColumns(usesCredits: boolean): Column<ClassPeriodRow>[] {
  const columns: Column<ClassPeriodRow>[] = [
    { chave: "turma", rotulo: "Turma", tipo: "texto", valor: (row) => row.turma },
    {
      chave: "horario",
      rotulo: "Horário",
      tipo: "texto",
      valor: (row) => row.horario,
    },
    { chave: "vagas", rotulo: "Vagas", tipo: "numero", valor: (row) => row.vagas },
    {
      chave: "preenchidas",
      rotulo: "Preenchidas",
      tipo: "numero",
      valor: (row) => row.preenchidas,
    },
    {
      chave: "pedidos",
      rotulo: "Pedidos",
      tipo: "numero",
      valor: (row) => row.pedidos,
    },
  ];
  if (usesCredits) {
    columns.push({
      chave: "preco_medio",
      rotulo: "Preço médio π",
      tipo: "numero",
      valor: (row) => row.preco_medio,
      escreve: (row) => number(row.preco_medio),
    });
  }
  columns.push({
    chave: "aprovacoes",
    rotulo: "Aprovações",
    tipo: "numero",
    valor: (row) => row.aprovacoes,
  });
  return columns;
}

function bidColumns(round: number, usesCredits: boolean): Column<Line>[] {
  const bid = (line: Line) => line.request.lances[round - 1] ?? 0;
  const columns: Column<Line>[] = [
    {
      chave: "aluno",
      rotulo: "Aluno",
      tipo: "texto",
      valor: (line) => line.request.nome,
    },
    {
      chave: "turma",
      rotulo: "Turma",
      tipo: "texto",
      valor: (line) => line.request.turma,
    },
    {
      chave: "cr",
      rotulo: "CR",
      tipo: "numero",
      valor: (line) => line.request.cr,
      escreve: (line) => number(line.request.cr),
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
      valor: (line) => (settledTone(line.outcome) ? line.request.nota : null),
      escreve: (line) =>
        settledTone(line.outcome) && line.request.nota !== null ? (
          <span className={line.outcome.tone}>
            {formatRatio(line.request.nota)}
          </span>
        ) : (
          "—"
        ),
    }
  );

  if (usesCredits) {
    columns.push({
      chave: "pago",
      rotulo: "Pago",
      tipo: "numero",
      valor: (line) => (settledTone(line.outcome) ? line.request.pago : null),
    });
  }

  return columns;
}
