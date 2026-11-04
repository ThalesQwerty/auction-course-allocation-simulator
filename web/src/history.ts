import { withUnlocks } from "./curriculum";
import { COMPARISON_ARMS, creditReturnLabel, horizonFor } from "./types";
import type { PerformanceProfile, Profile } from "./types";
import type {
  CompareRequest,
  CompareResponse,
  EvolveRequest,
  EvolveResponse,
  Scenario,
} from "./types";

export interface ComparisonRun {
  kind: "comparison";
  id: string;
  at: string; // ISO 8601
  config: CompareRequest;
  result: CompareResponse;
}

export interface EvolutionRun {
  kind: "evolution";
  id: string;
  at: string; // ISO 8601
  config: EvolveRequest;
  result: EvolveResponse;
}

export type HistoryEntry = ComparisonRun | EvolutionRun;

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
 * como converter — a tela leria `undefined` onde espera número.
 *
 * A **v5** (04/11/2026) quebrou pelo mesmo motivo, e é o terceiro caso da
 * mesma espécie: a nota deixou de sair de uma Beta sobre (0, 1) elevada a um
 * expoente e passa a sair de uma normal dividida censurada em [0, 10]. O
 * perfil de desempenho da v4 traz média e concentração de uma distribuição que
 * não existe mais, e não há tradução — a família mudou, não a parametrização.
 * Junto saíram o ganho por utilidade (a utilidade não mexe mais na nota) e o
 * ganho por recursada (quem calibra isso é a dificuldade). */
const STORAGE_KEY = "leilao.historico.v5";

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

export function newEvolution(
  config: EvolveRequest,
  result: EvolveResponse
): EvolutionRun {
  return { kind: "evolution", ...stamp(), config, result };
}

/** O cenário de uma execução gravada antes de 31/10/2026, traduzido para os
 * campos de hoje. Sem isto uma entrada antiga derruba a lista inteira — o
 * rótulo lê campos que não existem lá — ou reexecuta calada com outro cenário.
 *
 * **Disponibilidade**: é o único eixo que ainda tem tradução. Quando ela não
 * está gravada, a execução é de um modelo em que ninguém excluía, e entra
 * praticamente cheia — para que reexecutar reproduza o resultado antigo, que é
 * o que a lista promete.
 *
 * O eixo de desempenho não aparece aqui: a chave de armazenamento sobe quando
 * ele muda de família, porque traduzir média de Beta em nota média seria
 * inventar um cenário que ninguém rodou. */
function migrateScenario<
  T extends {
    performance_profiles: PerformanceProfile[];
    availability_profiles: Profile[];
  }
>(config: T): T {
  const migrated = { ...config };
  if (!Array.isArray(config.availability_profiles)) {
    migrated.availability_profiles = [
      { name: "cheia", mode_hours: 1, full_load_rate: 0.999 },
    ];
  }
  return migrated;
}

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    // Grade legada ainda pode trazer `prerequisites` no lugar de `unlocks`;
    // o resto do cenário legado passa por `migrateScenario`. O genérico
    // preserva o tipo de cada entrada: espalhar o cenário migrado apagaria a
    // união discriminada e a tela não saberia mais qual painel desenhar.
    const migrate = <T extends HistoryEntry>(entry: T): T =>
      ({
        ...entry,
        config: migrateScenario({
          ...entry.config,
          disciplines: withUnlocks(entry.config.disciplines ?? []),
        }),
      }) as T;
    return (parsed as HistoryEntry[]).map(migrate);
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

/** Uma execução gravada em disco pela API, de volta para a lista.
 *
 * O arquivo tem exatamente o formato de uma entrada daqui — é por isso que
 * carregar é só acrescentar. O `id` é novo: ele identifica a entrada *nesta*
 * lista, e o mesmo arquivo carregado duas vezes vira duas entradas em vez de
 * uma substituir a outra calada.
 *
 * O cenário passa pela mesma migração do histórico do navegador, de modo que
 * um arquivo gravado por uma versão anterior do motor continua abrindo. */
export function entryFromFile(text: string): HistoryEntry {
  const parsed = JSON.parse(text);
  if (parsed?.kind !== "evolution" && parsed?.kind !== "comparison") {
    throw new Error("arquivo não é um resultado do simulador");
  }
  if (!parsed.config || !parsed.result) {
    throw new Error("arquivo sem cenário ou sem resultado");
  }
  return {
    ...parsed,
    ...stamp(),
    // A data do arquivo vale mais que a de agora: é quando a simulação rodou.
    at: typeof parsed.at === "string" ? parsed.at : new Date().toISOString(),
    config: migrateScenario({
      ...parsed.config,
      disciplines: withUnlocks(parsed.config.disciplines ?? []),
    }),
  } as HistoryEntry;
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
  const { rounds, disciplines } = config;
  const periods = horizonFor(config.entry_periods, config.max_residence);
  // Uma coorte por período *com ingresso*: a população é o que entra por
  // período vezes a quantidade desses períodos, não vezes |T|.
  const students = config.students_per_period * config.entry_periods;
  const rodadas = rounds === 1 ? "1 rodada" : `${rounds} rodadas`;
  // O ciclo de vida muda o resultado inteiro, não só a escala: duas execuções
  // que só diferem nele precisam se distinguir. E como |T| é derivado dos dois
  // números, mostrá-lo sozinho esconderia qual deles mudou.
  const horizonte =
    config.entry_periods < periods
      ? `${periods} períodos (${config.entry_periods} com ingresso, jubila em ${config.max_residence})`
      : `${periods} períodos`;
  // Os perfis entram pela contagem, não pelos parâmetros: o que distingue
  // duas execuções à primeira vista é quantos grupos a população tinha, e a
  // lista inteira não caberia num rótulo de uma linha.
  const perfis = (axis: readonly { name: string }[]) =>
    `${axis.length} ${axis.length === 1 ? "perfil" : "perfis"}`;
  const populacao = [
    `desempenho: ${perfis(config.performance_profiles)}`,
    `disponibilidade: ${perfis(config.availability_profiles)}`,
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
  // com poucas seeds a dispersão da caixa mal se lê. E são os braços **que
  // rodaram**, não os dois canônicos: rodar um só é metade do tempo e metade
  // do que a tela mostra.
  const arms = run.config.arms?.length ?? COMPARISON_ARMS.length;
  return `${run.config.runs} seeds × ${arms} ${
    arms === 1 ? "modelo" : "modelos"
  } · ${describeScenario(run.config, { withCreditReturn: false })}`;
}

export function describeEvolution(run: EvolutionRun): string {
  // Gerações e observações primeiro: são os dois números que dizem quanto a
  // rodada custou e quanta resolução ela tem.
  const generations = run.result.generations.length;
  return (
    `${generations} ${generations === 1 ? "geração" : "gerações"}` +
    ` × ${run.config.observations} obs` +
    `${run.result.neutral ? " · controle negativo" : ""}` +
    ` · ${describeScenario(run.config, { withCreditReturn: false })}`
  );
}

export const describeEntry = (entry: HistoryEntry): string =>
  entry.kind === "evolution" ? describeEvolution(entry) : describeComparison(entry);
