import { creditReturnLabel } from "./types";
import type { SimulateRequest, SimulateResponse } from "./types";

/** Uma simulação já executada, guardada para consulta posterior. */
export interface SimulationRun {
  id: string;
  at: string; // ISO 8601
  config: SimulateRequest;
  result: SimulateResponse;
}

/** A versão faz parte da chave porque o formato do resultado mudou com o
 * modelo: a v1 guardava recortes por curso (`by_course`) e um `overall` que era
 * só as métricas. Não há como converter uma execução daquelas — os cursos
 * deixaram de existir e a conclusão passou a exigir a grade inteira —, então as
 * antigas simplesmente não são lidas, em vez de aparecerem meio vazias. */
const STORAGE_KEY = "leilao.historico.v2";

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
    return (parsed as SimulationRun[]).map((run) => ({
      ...run,
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
  const { periods, rounds, disciplines, credit_return, aptitude_profiles, affinity_profiles } =
    run.config;
  // Uma geração por período *com ingresso*: a população é o que entra por
  // período vezes L, não vezes |T|.
  const entrySpan = Math.min(run.config.entry_periods ?? periods, periods);
  const students = run.config.students_per_period * entrySpan;
  const rodadas = rounds === 1 ? "1 rodada" : `${rounds} rodadas`;
  // A fase de drenagem e o prazo de jubilamento mudam o resultado inteiro, não
  // só a escala: duas execuções que só diferem neles precisam se distinguir.
  const horizonte =
    entrySpan < periods ? `${periods} períodos (${entrySpan} com ingresso)` : `${periods} períodos`;
  // Um eixo com um perfil só é a população homogênea — o default —, e dizer
  // "1 perfil" não distingue execução nenhuma. Só entra quando há comparação.
  const perfis = [
    aptitude_profiles.length > 1 ? `${aptitude_profiles.length} aptidões` : null,
    affinity_profiles.length > 1 ? `${affinity_profiles.length} afinidades` : null,
  ].filter(Boolean);
  // A política de retorno entra no resumo porque é o eixo de experimentação da
  // Seção 7.3.2: duas execuções que só diferem nela precisam se distinguir na
  // barra lateral.
  return (
    `${horizonte} × ${rodadas} · ${disciplines.length} disciplinas · ${students} alunos` +
    (perfis.length ? ` · ${perfis.join(", ")}` : "") +
    ` · retorno ${creditReturnLabel(credit_return)}`
  );
}
