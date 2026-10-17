import { withUnlocks } from "./curriculum";
import { creditReturnLabel } from "./types";
import type {
  CompareRequest,
  CompareResponse,
  SimulateRequest,
  SimulateResponse,
} from "./types";

/** Uma execução já feita, guardada para consulta posterior. São dois tipos, e
 * `kind` diz qual: uma **simulação** (um cenário, uma seed, todos os gráficos
 * e a tela por aluno) ou uma **comparação** (o mesmo cenário nos dois
 * mecanismos, N seeds de cada lado, só as métricas principais em boxplot).
 *
 * As duas convivem na mesma lista porque é a mesma pergunta em escalas
 * diferentes, e porque o histórico é por data: quem rodou um cenário e depois
 * o comparou quer os dois ali, em ordem. */
export interface SimulationRun {
  kind: "simulation";
  id: string;
  at: string; // ISO 8601
  config: SimulateRequest;
  result: SimulateResponse;
}

export interface ComparisonRun {
  kind: "comparison";
  id: string;
  at: string; // ISO 8601
  config: CompareRequest;
  result: CompareResponse;
}

export type HistoryEntry = SimulationRun | ComparisonRun;

/** A versão faz parte da chave porque o formato do resultado mudou com o
 * modelo: a v1 guardava recortes por curso (`by_course`) e um `overall` que era
 * só as métricas. Não há como converter uma execução daquelas — os cursos
 * deixaram de existir e a conclusão passou a exigir a grade inteira —, então as
 * antigas simplesmente não são lidas, em vez de aparecerem meio vazias.
 *
 * A v2 continuou valendo com as comparações: `kind` era campo novo, e uma
 * entrada gravada antes dele não tinha como ser outra coisa senão uma
 * simulação. A **v3** (08/10/2026) quebrou de novo, e pelo mesmo motivo da v1:
 * os perfis de aluno saíram do modelo. Uma execução da v2 traz `by_aptitude`,
 * `by_affinity` e um cenário sem as duas normais que o substituíram, e não há
 * como converter — a tela leria `undefined` onde espera número. */
const STORAGE_KEY = "leilao.historico.v3";

/** Teto de execuções guardadas: cada resultado carrega todas as séries e todos
 * os alunos, então o histórico é podado pelas mais antigas. */
export const MAX_RUNS = 20;

/** O detalhe por aluno (`result.histories`) é ~20x maior que o resto do
 * resultado — 1 MB num cenário de 8 períodos, contra 51 kB. Guardá-lo estouraria
 * a cota do navegador em poucas execuções, então ele fica de fora do
 * localStorage e é reconstruído sob demanda re-executando a simulação, que é
 * determinística pela seed. Uma comparação não tem o que podar: ela já guarda
 * só cinco números por execução. */
function detachHistories(entry: HistoryEntry): HistoryEntry {
  return entry.kind === "comparison"
    ? entry
    : { ...entry, result: { ...entry.result, histories: [] } };
}

/** Se o detalhe por aluno desta execução está em memória nesta sessão. */
export function hasHistories(run: SimulationRun): boolean {
  return run.result.histories.length > 0 || run.result.students.length === 0;
}

const stamp = () => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  at: new Date().toISOString(),
});

export function newRun(config: SimulateRequest, result: SimulateResponse): SimulationRun {
  return { kind: "simulation", ...stamp(), config, result };
}

export function newComparison(
  config: CompareRequest,
  result: CompareResponse
): ComparisonRun {
  return { kind: "comparison", ...stamp(), config, result };
}

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return (parsed as HistoryEntry[]).map((entry) => {
      // Entradas gravadas antes das comparações existirem não têm `kind`, e
      // não havia outra coisa que elas pudessem ser. Grade legada ainda pode
      // trazer `prerequisites` no lugar de `unlocks`.
      const disciplines = withUnlocks(entry.config.disciplines ?? []);
      if (entry.kind === "comparison") {
        return { ...entry, config: { ...entry.config, disciplines } };
      }
      return {
        ...entry,
        kind: "simulation" as const,
        config: { ...entry.config, disciplines },
        result: { ...entry.result, histories: entry.result?.histories ?? [] },
      };
    });
  } catch {
    // localStorage indisponível (modo privado) ou conteúdo corrompido
    return [];
  }
}

/** Grava o histórico, descartando as execuções mais antigas enquanto o
 * navegador recusar por falta de espaço. Devolve o que de fato coube. */
export function saveHistory(entries: HistoryEntry[]): HistoryEntry[] {
  let kept = entries.slice(0, MAX_RUNS);
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

/** Resumo de uma linha do cenário, para distinguir execuções do mesmo minuto.
 * Vale para os dois tipos: a comparação roda exatamente o mesmo cenário, e é o
 * que ela acrescenta — o número de execuções — que a distingue. */
function describeScenario(
  config: SimulateRequest | CompareRequest,
  { withCreditReturn }: { withCreditReturn: boolean }
): string {
  const { periods, rounds, disciplines } = config;
  // Uma geração por período *com ingresso*: a população é o que entra por
  // período vezes L, não vezes |T|.
  const entrySpan = Math.min(config.entry_periods ?? periods, periods);
  const students = config.students_per_period * entrySpan;
  const rodadas = rounds === 1 ? "1 rodada" : `${rounds} rodadas`;
  // A fase de drenagem muda o resultado inteiro, não só a escala: duas
  // execuções que só diferem nela precisam se distinguir.
  const horizonte =
    entrySpan < periods ? `${periods} períodos (${entrySpan} com ingresso)` : `${periods} períodos`;
  // As duas normais entram só quando saem do default: num cenário montado a
  // partir de um preset elas distinguem execuções que, de resto, são iguais.
  const populacao = [
    `n ~ ${config.grade_mean.toLocaleString("pt-BR")} ± ${config.grade_stddev.toLocaleString("pt-BR")}`,
    `u σ ${config.utility_sigma.toLocaleString("pt-BR")}`,
  ];
  return (
    `${horizonte} × ${rodadas} · ${disciplines.length} disciplinas · ${students} alunos` +
    ` · ${populacao.join(", ")}` +
    // Numa comparação o retorno não é do cenário: é o eixo do experimento, e
    // dizer "retorno nenhum" ali descreveria só um dos três braços.
    (withCreditReturn && "credit_return" in config
      ? ` · retorno ${creditReturnLabel(config.credit_return)}`
      : "")
  );
}

export function describeRun(run: SimulationRun): string {
  // A política de retorno entra no resumo porque é o eixo de experimentação da
  // Seção 7.3.2: duas execuções que só diferem nela precisam se distinguir na
  // barra lateral.
  return describeScenario(run.config, { withCreditReturn: true });
}

/** Quantos modelos uma comparação põe lado a lado. Espelha
 * `leilao.comparison.ARMS`; fica aqui para o resumo da barra lateral não
 * depender da tela que desenha os gráficos. */
const COMPARED_MODELS = 3;

export function describeComparison(run: ComparisonRun): string {
  // O número de execuções vem primeiro: é o que muda a leitura do resultado —
  // com poucas seeds a dispersão da caixa mal se lê.
  return `${run.config.runs} seeds × ${COMPARED_MODELS} modelos · ${describeScenario(
    run.config,
    { withCreditReturn: false }
  )}`;
}

export const describeEntry = (entry: HistoryEntry): string =>
  entry.kind === "comparison" ? describeComparison(entry) : describeRun(entry);
