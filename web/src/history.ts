import { creditReturnLabel } from "./types";
import type { SimulateRequest, SimulateResponse } from "./types";

/** Uma simulação já executada, guardada para consulta posterior. */
export interface SimulationRun {
  id: string;
  at: string; // ISO 8601
  config: SimulateRequest;
  result: SimulateResponse;
}

const STORAGE_KEY = "leilao.historico.v1";

/** Teto de execuções guardadas: cada resultado carrega todas as séries e todos
 * os alunos, então o histórico é podado pelas mais antigas. */
export const MAX_RUNS = 20;

/** O detalhe por aluno (`result.histories`) é ~20x maior que o resto do
 * resultado — 1 MB num cenário de 8 períodos, contra 51 kB. Guardá-lo estouraria
 * a cota do navegador em poucas execuções, então ele fica de fora do
 * localStorage e é reconstruído sob demanda re-executando a simulação, que é
 * determinística pela seed. */
function detachHistories(run: SimulationRun): SimulationRun {
  return { ...run, result: { ...run.result, histories: [] } };
}

/** Se o detalhe por aluno desta execução está em memória nesta sessão. */
export function hasHistories(run: SimulationRun): boolean {
  return run.result.histories.length > 0 || run.result.students.length === 0;
}

export function newRun(config: SimulateRequest, result: SimulateResponse): SimulationRun {
  return { id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, at: new Date().toISOString(), config, result };
}

export function loadHistory(): SimulationRun[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    // Execuções gravadas antes destes campos existirem não os têm. O nível de
    // aprendizado era fixo em 1 ponto por recursada, então é esse o valor que
    // descreve essas execuções antigas — não o padrão atual. A única política
    // de retorno que existia era a nula.
    return (parsed as SimulationRun[]).map((run) => ({
      ...run,
      config: {
        ...run.config,
        learning_gain: run.config.learning_gain ?? 1,
        credit_return: run.config.credit_return ?? "none",
        // Antes destes campos existirem o ingresso era em todos os períodos e
        // não havia prazo — exatamente o que `null` e 0 significam hoje.
        entry_periods: run.config.entry_periods ?? null,
        max_residence: run.config.max_residence ?? 0,
      },
      result: { ...run.result, histories: run.result.histories ?? [] },
    }));
  } catch {
    // localStorage indisponível (modo privado) ou conteúdo corrompido
    return [];
  }
}

/** Grava o histórico, descartando as execuções mais antigas enquanto o
 * navegador recusar por falta de espaço. Devolve o que de fato coube. */
export function saveHistory(runs: SimulationRun[]): SimulationRun[] {
  let kept = runs.slice(0, MAX_RUNS);
  while (kept.length > 0) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(kept.map(detachHistories)));
      return kept;
    } catch {
      kept = kept.slice(0, kept.length - 1);
    }
  }
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // sem localStorage não há nada a limpar
  }
  return kept;
}

/** "01/10/2026, 14:32" — rótulo de cada execução na barra lateral. */
export function formatRunDate(at: string): string {
  const date = new Date(at);
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Resumo de uma linha do cenário, para distinguir execuções do mesmo minuto. */
export function describeRun(run: SimulationRun): string {
  const { periods, rounds, courses, credit_return, max_residence } = run.config;
  // Uma geração por período *com ingresso*: a população é o que cada curso
  // recebe por geração vezes L, não vezes |T|.
  const entrySpan = Math.min(run.config.entry_periods ?? periods, periods);
  const students =
    courses.reduce((sum, course) => sum + course.students_per_generation, 0) * entrySpan;
  const rodadas = rounds === 1 ? "1 rodada" : `${rounds} rodadas`;
  // A fase de drenagem e o prazo de jubilamento mudam o resultado inteiro, não
  // só a escala: duas execuções que só diferem neles precisam se distinguir.
  const horizonte =
    entrySpan < periods ? `${periods} períodos (${entrySpan} com ingresso)` : `${periods} períodos`;
  const prazo = max_residence ? ` · jubilamento em ${max_residence}` : "";
  // A política de retorno entra no resumo porque é o eixo de experimentação da
  // Seção 7.3.2: duas execuções que só diferem nela precisam se distinguir na
  // barra lateral.
  return (
    `${horizonte} × ${rodadas} · ${courses.length} cursos · ${students} alunos` +
    ` · retorno ${creditReturnLabel(credit_return)}${prazo}`
  );
}
