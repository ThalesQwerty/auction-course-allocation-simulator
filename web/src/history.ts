import { entryClasses, withUnlocks } from "./curriculum";
import { cohortSize } from "./equations";
import { defaultScenario } from "./presets";
import { readEntries, requestPersistence, writeEntries } from "./historyStore";
import { COMPARISON_ARMS, horizonFor } from "./types";
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
 * `students_per_period` como campo do cenário (hoje a coorte sai do ingresso
 * por turma de entrada) e não traz eixo de estratégia nenhum; reexecutá-la
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
 * **Crédito**: `base_credits` era o Γ_min somado todo período; ele virou
 * `min_credits`, o piso do orçamento. O número é o mesmo e o nome é o que
 * muda, mas a regra não: uma execução gravada antes de 15/11/2026 rodou com o
 * ganho base, e reexecutá-la dará outro resultado.
 *
 * O **multiplicador** entra em 1, que é o `ratio` de então — o braço com
 * retorno rodava `round(nota/10 · preço)`, que é exatamente o `k = 1` de
 * hoje: o piso que tomou esse lugar em 15/11/2026 voltou a ser arredondamento
 * em 17/11/2026. As outras três políticas não se traduzem em `k`
 * nenhum, e também nunca chegaram a rodar: numa comparação o retorno do
 * cenário era ignorado e cada braço impunha o seu.
 *
 * A **fração da exclusão** entra em 0. Ela valia `preço // 2` só sob `ratio`,
 * o que não se escreve como fração única do cenário.
 *
 * O eixo de desempenho não aparece aqui: a chave de armazenamento sobe quando
 * ele muda de família, porque traduzir média de Beta em nota média seria
 * inventar um cenário que ninguém rodou. */
function migrateScenario<T extends Record<string, unknown>>(config: T): T {
  const migrated = migrateInterest(config);
  const campos = migrated as Record<string, unknown>;
  if (typeof campos.min_credits !== "number") {
    campos.min_credits =
      typeof campos.base_credits === "number" ? campos.base_credits : 12;
    delete campos.base_credits;
  }
  // O multiplicador do retorno e a fração da excluída saíram do cenário em
  // 24/11/2026: o primeiro virou constante, a segunda virou sempre zero.
  delete campos.return_multiplier;
  delete campos.exclusion_refund_rate;
  // Execução gravada antes de 16/11/2026 não tem turno nem horário, e rodou
  // num modelo em que a turma não tinha nenhum dos dois. Reexecutá-la dará
  // outro resultado — o que os padrões fazem aqui é só impedir que a API caia
  // calada em outro cenário ainda.
  if (typeof campos.slots !== "number") {
    // Execução gravada com os dois turnos traz `day_slots`/`night_slots`; o
    // modelo de régua única soma os dois, que é o número de horários que
    // aquela grade de fato tinha.
    const dia = typeof campos.day_slots === "number" ? campos.day_slots : 12;
    const noite = typeof campos.night_slots === "number" ? campos.night_slots : 6;
    campos.slots = dia + noite;
  }
  delete campos.day_slots;
  delete campos.night_slots;
  delete campos.routine_profiles;
  delete campos.class_difficulty_levels;
  // Execução gravada antes da janela estacionária (19/11/2026) traz
  // `entry_periods` e um horizonte de ciclo de vida. O que mais se aproxima
  // dela é observar o que sobrava depois da residência; reexecutá-la dará
  // outro resultado de qualquer modo, porque o ingresso passou a ser contínuo.
  if (typeof campos.observation_periods !== "number") {
    const entradas =
      typeof campos.entry_periods === "number" ? campos.entry_periods : 8;
    campos.observation_periods = Math.max(1, entradas);
  }
  delete campos.entry_periods;
  // A coorte deixou de ser digitada em 24/11/2026: o que se digita é o
  // ingresso **por turma de entrada**, e a coorte sai como produto. Não há
  // tradução — a coorte gravada não costuma ser divisível pelas turmas de
  // entrada —, então o que havia é descartado e a execução antiga volta com o
  // ingresso do cenário padrão. Reexecutá-la dará outra população.
  if (typeof campos.students_per_entry_class !== "number") {
    campos.students_per_entry_class = defaultScenario().students_per_entry_class;
  }
  delete campos.students_per_period;
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
function describeScenario(config: Scenario | CompareRequest): string {
  const { rounds, disciplines } = config;
  const periods = horizonFor(config.max_residence, config.observation_periods);
  // Em regime a população é a coorte vezes o prazo de jubilamento: entra uma
  // por período e sai uma, de `t = max_residence` em diante. A coorte, por sua
  // vez, é o ingresso por turma de entrada vezes as turmas dela.
  const students =
    cohortSize(config.students_per_entry_class, entryClasses(disciplines)) *
    config.max_residence;
  const rodadas = rounds === 1 ? "1 rodada" : `${rounds} rodadas`;
  // O ciclo de vida muda o resultado inteiro, não só a escala: duas execuções
  // que só diferem nele precisam se distinguir. E como |T| é derivado dos dois
  // números, mostrá-lo sozinho esconderia qual deles mudou.
  const horizonte =
    config.max_residence > 0
      ? `${periods} períodos (${config.max_residence} de pré-população, ${config.observation_periods} medidos)`
      : `${periods} períodos`;
  // Os perfis entram pela contagem, não pelos parâmetros: o que distingue
  // duas execuções à primeira vista é quantos grupos a população tinha, e a
  // lista inteira não caberia num rótulo de uma linha.
  const numero = (value: number) => value.toLocaleString("pt-BR");
  const populacao = [
    `nota ${numero(config.performance.mode_grade)}`,
    `carga ${numero(config.availability.mode_hours)} h`,
    // A seletividade vive em milésimos — `numero` arredondaria a três casas
    // e apagaria a diferença entre dois cenários.
    `seletividade ${config.selectivity_median.toLocaleString("pt-BR", {
      maximumFractionDigits: 5,
    })}`,
    `interesse σ ${numero(config.interest_sigma)}`,
    // Uma faixa a mais que os cortes, por eixo. O do crédito não entra: ele
    // só existe no leilão, e o resumo descreve o cenário, não o braço.
    `CR em ${config.grade_cuts.length + 1}, reserva em ${
      config.reserve_cuts.length + 1
    }`,
  ];
  return (
    `${horizonte} × ${rodadas} · ${disciplines.length} disciplinas · ${students} alunos` +
    ` · ${populacao.join(", ")}`
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
  } · ${describeScenario(run.config)}`;
}

export const describeEntry = (entry: HistoryEntry): string =>
  describeComparison(entry);
