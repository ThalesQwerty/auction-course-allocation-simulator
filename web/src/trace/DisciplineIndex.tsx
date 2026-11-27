import { useMemo } from "react";
import { formatCount, formatRatio } from "../charts";
import { DataTable } from "../tables/DataTable";
import type { Column } from "../tables/DataTable";
import type { DisciplineIndexPayload, DisciplineIndexRow } from "../types";

const percent = (value: number | null) =>
  value === null
    ? "—"
    : `${(value * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%`;

const number = (value: number | null) =>
  value === null ? "—" : formatRatio(value);

export function DisciplineIndex({
  payload,
  usesCredits,
  escolhido,
  aoEscolher,
}: {
  payload: DisciplineIndexPayload;
  usesCredits: boolean;
  escolhido?: string;
  aoEscolher: (discipline: DisciplineIndexRow) => void;
}) {
  const columns = useMemo<Column<DisciplineIndexRow>[]>(() => {
    const base: Column<DisciplineIndexRow>[] = [
      {
        chave: "disciplina",
        rotulo: "Disciplina",
        tipo: "texto",
        valor: (row) => row.disciplina,
        filtro: true,
      },
      {
        chave: "nivel",
        rotulo: "Nível",
        tipo: "numero",
         // A optativa ordena por último: ela não pertence a período da grade.
        valor: (row) => (row.optativa ? null : row.nivel),
        escreve: (row) => (row.optativa ? "optativa" : (row.nivel ?? "—")),
        filtro: true,
      },
      {
        chave: "carga",
        rotulo: "Carga",
        tipo: "numero",
        valor: (row) => row.carga,
        escreve: (row) => `${row.carga} h`,
        filtro: true,
      },
      {
        chave: "turmas",
        rotulo: "Turmas",
        tipo: "numero",
        valor: (row) => row.turmas,
        filtro: true,
      },
      {
        chave: "vagas",
        rotulo: "Vagas",
        tipo: "numero",
        valor: (row) => row.vagas,
        filtro: true,
      },
      {
        chave: "pedidos",
        rotulo: "Pedidos por período",
        tipo: "numero",
        valor: (row) => row.pedidos,
        escreve: (row) => (row.pedidos === null ? "—" : formatCount(row.pedidos)),
        filtro: true,
      },
      {
        chave: "demanda_por_vaga",
        rotulo: "Demanda por vaga",
        tipo: "numero",
        valor: (row) => row.demanda_por_vaga,
        escreve: (row) => number(row.demanda_por_vaga),
        filtro: true,
      },
      {
        chave: "preenchimento",
        rotulo: "Preenchimento",
        tipo: "numero",
        valor: (row) => row.preenchimento,
        escreve: (row) => percent(row.preenchimento),
        filtro: true,
      },
    ];

    const price: Column<DisciplineIndexRow>[] = [
      {
        chave: "preco_medio",
        rotulo: "Preço médio π",
        tipo: "numero",
        valor: (row) => row.preco_medio,
        escreve: (row) => number(row.preco_medio),
        filtro: true,
      },
    ];

    const rest: Column<DisciplineIndexRow>[] = [
      {
        chave: "nota_media",
        rotulo: "Nota média",
        tipo: "numero",
        valor: (row) => row.nota_media,
        escreve: (row) => number(row.nota_media),
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
        chave: "exclusoes",
        rotulo: "Exclusões",
        tipo: "numero",
        valor: (row) => row.exclusoes,
        filtro: true,
      },
    ];

    return usesCredits ? [...base, ...price, ...rest] : [...base, ...rest];
  }, [usesCredits]);

  return (
    <div className="panel">
      <header className="chart-part-head">
        <h3>
          {payload.disciplinas.length === 1
            ? "1 disciplina"
            : `${payload.disciplinas.length} disciplinas`}{" "}
          · {payload.disciplinas.reduce((total, row) => total + row.turmas, 0)} turmas
        </h3>
      </header>
      <DataTable
        rows={payload.disciplinas}
        columns={columns}
        chave={(row) => row.disciplina}
        inicial={{ chave: "nivel", desc: false }}
        pagina={25}
        escolhido={escolhido}
        aoEscolher={aoEscolher}
        vazio="Nenhuma disciplina cabe nos filtros."
      />
    </div>
  );
}
