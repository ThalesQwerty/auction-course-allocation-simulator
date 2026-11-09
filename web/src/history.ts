import { withUnlocks } from "./curriculum";
import { cohortSize } from "./equations";
import { readEntries, requestPersistence, writeEntries } from "./historyStore";
import { COMPARISON_ARMS, creditReturnLabel, horizonFor } from "./types";
import type { PerformanceProfile, Profile } from "./types";
import type { CompareRequest, CompareResponse, Scenario } from "./types";

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
 * como converter — a tela leria `undefined` onde espera número.
 *
 * A **v5** (04/11/2026) quebrou pelo mesmo motivo, e é o terceiro caso da
 * mesma espécie: a nota deixou de sair de uma Beta sobre (0, 1) elevada a um
 * expoente e passa a sair de uma normal dividida censurada em [0, 10]. O
 * perfil de desempenho da v4 traz média e concentração de uma distribuição que
 * não existe mais, e não há tradução — a família mudou, não a parametrização.
 * Junto saíram o ganho por utilidade (a utilidade não mexe mais na nota) e o
 * ganho por recursada (quem calibra isso é a dificuldade).
 *
 * A **v6** (05/11/2026) é a quarta quebra da mesma espécie, e a maior: o bem
 * alocado deixou de ser a disciplina e passou a ser a **turma**, e o perfil do
 * aluno ganhou dois eixos de estratégia — seletividade e concentração — no
 * lugar do algoritmo genético, que saiu do escopo. Uma execução da v5 traz
 * `students_per_period` como campo do cenário (hoje ele é derivado dos
 * exemplares por perfil) e não traz eixo de estratégia nenhum; reexecutá-la
 * mandaria à API um cenário que ela recusa. Junto some a entrada evolutiva:
 * `kind: "evolution"` não tem mais tela.
 *
 * Desde 09/11/2026 o histórico mora no **IndexedDB** (`historyStore`), sob a
 * mesma versão. A chave do `localStorage` continua aqui só para a migração:
 * o que estiver nela é lido uma vez, copiado e apagado. */
const STORAGE_KEY = "leilao.historico.v6";
const STORE_KEY = "historico.v6";

/** Teto de execuções guardadas. Não é limitação de espaço — o IndexedDB tem
 * cota de sobra —, é que uma lista maior que isso deixa de se escolher de
 * relance na barra lateral. */
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

/** Os nomes de antes de 04/11/2026, quando "utilidade" se partiu em duas
 * palavras: **interesse** é o sorteio normalizado, que σ e a estabilidade
 * governam e que o histograma retrata; **utilidade** é ele visto pelo
 * histórico do aluno. Os valores não mudaram — só a chave —, então a tradução
 * é exata. Se o nome novo já estiver lá, ele vence. */
const INTEREST_RENAMES = [
  ["utility_sigma", "interest_sigma"],
  ["utility_stability", "interest_stability"],
  ["utility_distribution", "interest_distribution"],
] as const;

/** Troca as chaves antigas pelas de `INTEREST_RENAMES`. Serve tanto ao cenário
 * quanto ao resultado de uma comparação, e aos cenários salvos — que guardam
 * os mesmos campos e passam pela mesma troca. */
export function withInterestNames<T extends object>(record: T): T {
  const migrated = { ...record } as Record<string, unknown>;
  for (const [old, current] of INTEREST_RENAMES) {
    if (!(old in migrated)) continue;
    if (migrated[current] === undefined) migrated[current] = migrated[old];
    delete migrated[old];
  }
  return migrated as T;
}

/** Os campos de interesse de um **cenário** gravado antes de 04/11/2026: as
 * chaves novas (`withInterestNames`) e o μ, que não existia. Ele era fixo em
 * 0, e é isso que entra — a tradução fiel do que rodou. Qualquer outro valor
 * daria o mesmo resultado, porque μ some na normalização; só a prévia mudaria. */
export function migrateInterest<T extends object>(config: T): T {
  const migrated = withInterestNames(config) as Record<string, unknown>;
  if (typeof migrated.interest_mean !== "number") migrated.interest_mean = 0;
  return migrated as T;
}

/** O cenário de uma execução gravada antes de 31/10/2026, traduzido para os
 * campos de hoje. Sem isto uma entrada antiga derruba a lista inteira — o
 * rótulo lê campos que não existem lá — ou reexecuta calada com outro cenário.
 *
 * **Interesse**: `utility_sigma` e `utility_stability` viraram `interest_*`,
 * e o μ ausente entra como 0 (`migrateInterest`). Sem a troca, reexecutar
 * mandaria o cenário sem os dois e a API cairia calada nos padrões.
 *
 * **Disponibilidade**: quando ela não está gravada, a execução é de um modelo em que ninguém excluía, e entra
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
  const migrated = migrateInterest(config);
  if (!Array.isArray(config.availability_profiles)) {
    migrated.availability_profiles = [
      { name: "cheia", mode_hours: 1, full_load_rate: 0.999 },
    ];
  }
  return migrated;
}

/** Grade legada ainda pode trazer `prerequisites` no lugar de `unlocks`; o
 * resto do cenário legado passa por `migrateScenario`. O genérico preserva o
 * tipo de cada entrada: espalhar o cenário migrado apagaria a união
 * discriminada e a tela não saberia mais qual painel desenhar. */
const migrateEntry = <T extends HistoryEntry>(entry: T): T =>
  ({
    ...entry,
    config: migrateScenario({
      ...entry.config,
      disciplines: withUnlocks(entry.config.disciplines ?? []),
    }),
    result: withInterestNames(entry.result),
  }) as T;

/** O histórico do `localStorage`, de antes do IndexedDB. Vazio quando não há
 * nada lá, ou quando o `localStorage` está indisponível ou corrompido. */
function readLegacy(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as HistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function dropLegacy(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // sem localStorage não há nada a limpar
  }
}

/** Lê o histórico. Na primeira vez depois da troca de armazenamento, o que
 * estava no `localStorage` é copiado para o IndexedDB e a chave antiga some
 * — só depois de a cópia ter sido gravada, para nada se perder no meio.
 *
 * Sem IndexedDB (navegador antigo, modo privado restrito), devolve o que o
 * `localStorage` tiver: a tela abre com o histórico, só não o grava. */
let loading: Promise<HistoryEntry[]> | null = null;

export function loadHistory(): Promise<HistoryEntry[]> {
  // Chamadas concorrentes (o StrictMode monta o efeito duas vezes) dividem a
  // mesma leitura, senão a migração correria duas vezes em paralelo.
  loading ??= readHistory().finally(() => (loading = null));
  return loading;
}

async function readHistory(): Promise<HistoryEntry[]> {
  requestPersistence();
  try {
    const stored = await readEntries<HistoryEntry>(STORE_KEY);
    if (stored !== undefined) return stored.map(migrateEntry);
    const legacy = readLegacy().slice(0, MAX_RUNS);
    await writeEntries(STORE_KEY, legacy);
    dropLegacy();
    return legacy.map(migrateEntry);
  } catch {
    return readLegacy().map(migrateEntry);
  }
}

/** Grava o histórico, podado a `MAX_RUNS`. Devolve o que de fato ficou
 * gravado: se o navegador recusar por falta de espaço, as mais antigas saem
 * até caber, como no `localStorage` — só que aqui isso não deve acontecer. */
export async function saveHistory(entries: HistoryEntry[]): Promise<HistoryEntry[]> {
  let kept = entries.slice(0, MAX_RUNS);
  while (true) {
    try {
      await writeEntries(STORE_KEY, kept);
      return kept;
    } catch (error) {
      const quota = (error as DOMException | null)?.name === "QuotaExceededError";
      if (!quota || kept.length === 0) return kept;
      kept = kept.slice(0, kept.length - 1);
    }
  }
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
  if (parsed?.kind !== "comparison") {
    throw new Error("arquivo não é uma comparação do simulador");
  }
  if (!parsed.config || !parsed.result) {
    throw new Error("arquivo sem cenário ou sem resultado");
  }
  // O mesmo corte que a chave de armazenamento faz com o histórico do
  // navegador, agora com um arquivo: sem os eixos de estratégia o cenário é
  // de antes de 05/11/2026, e reexecutá-lo mandaria à API um pedido que ela
  // recusa — a coorte era digitada e a atratividade era outro tipo de
  // grandeza. Não há tradução, e abrir meio vazio seria pior que recusar.
  if (!Array.isArray(parsed.config.selectivity_profiles)) {
    throw new Error(
      "arquivo de antes dos eixos de estratégia e das turmas — não há como convertê-lo"
    );
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
    result: withInterestNames(parsed.result),
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

/** Resumo de uma linha do cenário, para distinguir execuções do mesmo minuto. */
function describeScenario(
  config: Scenario | CompareRequest,
  { withCreditReturn }: { withCreditReturn: boolean }
): string {
  const { rounds, disciplines } = config;
  const periods = horizonFor(config.entry_periods, config.max_residence);
  // Uma coorte por período *com ingresso*: a população é a coorte vezes a
  // quantidade desses períodos, não vezes |T|. E a coorte é derivada dos
  // perfis — ver `equations.cohortSize`.
  const students = cohortSize(config) * config.entry_periods;
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
  const perfis = (axis: readonly unknown[]) =>
    `${axis.length} ${axis.length === 1 ? "perfil" : "perfis"}`;
  const populacao = [
    `desempenho: ${perfis(config.performance_profiles)}`,
    `disponibilidade: ${perfis(config.availability_profiles)}`,
    `seletividade: ${perfis(config.selectivity_profiles)}`,
    `concentração: ${perfis(config.concentration_profiles)}`,
    `interesse σ ${config.interest_sigma.toLocaleString("pt-BR")}`,
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
  // com poucas seeds a faixa interquartil mal se lê. E são os braços **que
  // rodaram**, não os dois canônicos: rodar um só é metade do tempo e metade
  // do que a tela mostra.
  const arms = run.config.arms?.length ?? COMPARISON_ARMS.length;
  return `${run.config.runs} seeds × ${arms} ${
    arms === 1 ? "modelo" : "modelos"
  } · ${describeScenario(run.config, { withCreditReturn: false })}`;
}

export const describeEntry = (entry: HistoryEntry): string =>
  describeComparison(entry);
