import { useMemo } from "react";
import { formatCount, formatRatio } from "../charts";
import { DataTable } from "../tables/DataTable";
import type { Column } from "../tables/DataTable";
import type { StudentIndexPayload, StudentIndexRow } from "../types";

const SAIDAS = ["formado", "jubilado"] as const;

const percent = (value: number | null) =>
  value === null ? "—" : `${(value * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%`;

const number = (value: number | null) =>
  value === null ? "—" : formatRatio(value);

export function StudentIndex({
  payload,
  usesCredits,
  escolhido,
  aoEscolher,
}: {
  payload: StudentIndexPayload;
  usesCredits: boolean;
  escolhido?: string;
  aoEscolher: (student: StudentIndexRow) => void;
}) {
  const columns = useMemo<Column<StudentIndexRow>[]>(() => {
    const base: Column<StudentIndexRow>[] = [
      {
        chave: "nome",
        rotulo: "Aluno",
        tipo: "texto",
        valor: (row) => row.nome,
        filtro: true,
      },
      {
        chave: "ingresso",
        rotulo: "Ingresso",
        tipo: "numero",
        valor: (row) => row.ingresso,
        filtro: true,
      },
      {
        chave: "periodos",
        rotulo: "Períodos ativos",
        tipo: "numero",
        valor: (row) => row.periodos,
        filtro: true,
      },
      {
        chave: "cr",
        rotulo: "CR",
        tipo: "numero",
        valor: (row) => row.cr,
        escreve: (row) => number(row.cr),
        filtro: true,
      },
      {
        chave: "intensidade",
        rotulo: "Intensidade de demanda",
        tipo: "numero",
        valor: (row) => row.intensidade,
        escreve: (row) => percent(row.intensidade),
        filtro: true,
      },
      {
        chave: "carga_aprovada",
        rotulo: "Horas aprovadas",
        tipo: "numero",
        valor: (row) => row.carga_aprovada,
        escreve: (row) => `${row.carga_aprovada} / ${payload.carga_obrigatoria}`,
        filtro: true,
      },
      {
        chave: "matriculas",
        rotulo: "Matrículas",
        tipo: "numero",
        valor: (row) => row.matriculas,
        filtro: true,
      },
      {
        chave: "aprovacoes",
        rotulo: "Aprovações",
        tipo: "numero",
        valor: (row) => row.aprovacoes,
        filtro: true,
      },
      {
        chave: "satisfacao",
        rotulo: "Satisfação média",
        tipo: "numero",
        valor: (row) => row.satisfacao,
        escreve: (row) => number(row.satisfacao),
        filtro: true,
      },
      {
        chave: "rodada_media",
        rotulo: "Rodada média",
        tipo: "numero",
        valor: (row) => row.rodada_media,
        escreve: (row) => number(row.rodada_media),
        filtro: true,
      },
      {
        chave: "disponibilidade",
        rotulo: "Disponibilidade média",
        tipo: "numero",
        valor: (row) => row.disponibilidade,
        escreve: (row) =>
          row.disponibilidade === null
            ? "—"
            : `${formatCount(row.disponibilidade)} h`,
        filtro: true,
      },
    ];

    const credits: Column<StudentIndexRow>[] = [
      {
        chave: "creditos_fim",
        rotulo: "Créditos no fim",
        tipo: "numero",
        valor: (row) => row.creditos_fim,
        filtro: true,
      },
      {
        chave: "creditos_gasto",
        rotulo: "Créditos gastos",
        tipo: "numero",
        valor: (row) => row.creditos_gasto,
        filtro: true,
      },
    ];

    const exit: Column<StudentIndexRow>[] = [
      {
        chave: "saida",
        rotulo: "Saída",
        tipo: "enum",
        ordem: SAIDAS,
        valor: (row) => row.saida,
        escreve: (row) =>
          row.saida_periodo === null
            ? row.saida
            : `${row.saida} no período ${row.saida_periodo}`,
        filtro: true,
      },
    ];

    return usesCredits ? [...base, ...credits, ...exit] : [...base, ...exit];
  }, [payload.carga_obrigatoria, usesCredits]);

  return (
    <div className="panel">
      <header className="chart-part-head">
        <h3>
          {payload.alunos.length === 1
            ? "1 aluno medido"
            : `${payload.alunos.length} alunos medidos`}
        </h3>
      </header>
      <DataTable
        rows={payload.alunos}
        columns={columns}
        chave={(row) => row.aluno}
        inicial={{ chave: "cr", desc: true }}
        pagina={25}
        escolhido={escolhido}
        aoEscolher={aoEscolher}
        vazio="Nenhum aluno cabe nos filtros."
      />
    </div>
  );
}
