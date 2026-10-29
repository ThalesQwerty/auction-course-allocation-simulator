import { withUnlocks } from "./curriculum";
import { COMPARISON_ARMS, creditReturnLabel } from "./types";
import type {
  CompareRequest,
  CompareResponse,
  Scenario,
} from "./types";

export interface ComparisonRun {
  kind: "comparison";
  id: string;
  at: string; // ISO 8601
  config: CompareRequest;
  result: CompareResponse;
}

export type HistoryEntry = ComparisonRun;

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

const stamp = () => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  at: new Date().toISOString(),
});

export function newComparison(
  config: CompareRequest,
  result: CompareResponse
): ComparisonRun {
  return { kind: "comparison", ...stamp(), config, result };
}

/** O cenário de uma execução gravada antes de 29/10/2026, traduzido para os
 * campos de hoje. Sem isto uma entrada antiga derruba a lista inteira — o
 * rótulo lê campos que não existem lá — ou reexecuta calada com outro cenário.
 *
 * **Aptidão**: era descrita pelos dois parâmetros de forma da Beta e passou a
 * ser média e concentração. É a mesma Beta vista do outro lado, com
 * `média = forma_1/(forma_1 + forma_2)` e `concentração = forma_1 + forma_2`.
 *
 * **Ganhos**: o `interest_coupling` virou `utility_gain` sem mudar de
 * significado, e o `grade_noise` deu lugar ao `retake_gain`. Este último não é
 * tradução — o choque não vira coeficiente —, então a execução antiga recebe o
 * padrão 1 e passa a valer o `D/t`, que é o que o choque já fazia em média. */
function migrateScenario<
  T extends {
    aptitude_mean: number;
    aptitude_concentration: number;
    utility_gain: number;
    retake_gain: number;
  }
>(config: T): T {
  const legacy = config as T & {
    aptitude_alpha?: number;
    aptitude_beta?: number;
    interest_coupling?: number;
  };
  const migrated = { ...config };
  if (typeof config.aptitude_mean !== "number") {
    const concentration = (legacy.aptitude_alpha ?? 4) + (legacy.aptitude_beta ?? 2);
    migrated.aptitude_mean = (legacy.aptitude_alpha ?? 4) / concentration;
    migrated.aptitude_concentration = concentration;
  }
  if (typeof config.utility_gain !== "number") {
    migrated.utility_gain = legacy.interest_coupling ?? 0;
  }
  if (typeof config.retake_gain !== "number") {
    migrated.retake_gain = 1;
  }
  return migrated;
}

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    // Grade legada ainda pode trazer `prerequisites` no lugar de `unlocks`;
    // o resto do cenário legado passa por `migrateScenario`.
    return (parsed as HistoryEntry[]).map((entry) => ({
      ...entry,
      config: migrateScenario({
        ...entry.config,
        disciplines: withUnlocks(entry.config.disciplines ?? []),
      }),
    }));
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
      localStorage.setItem(STORAGE_KEY, JSON.stringify(kept));
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
  config: Scenario | CompareRequest,
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
    `aptidão: média ${config.aptitude_mean.toLocaleString("pt-BR")} · concentração ${config.aptitude_concentration.toLocaleString("pt-BR")}`,
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

export function describeComparison(run: ComparisonRun): string {
  // O número de execuções vem primeiro: é o que muda a leitura do resultado —
  // com poucas seeds a dispersão da caixa mal se lê.
  return `${run.config.runs} seeds × ${COMPARISON_ARMS.length} modelos · ${describeScenario(
    run.config,
    { withCreditReturn: false }
  )}`;
}

export const describeEntry = (entry: HistoryEntry): string => describeComparison(entry);
