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

/** A versão faz parte da chave porque o formato do resultado mudou com o modelo: a v1 guardava recortes por curso (`by_course`) e um `overall` que era só as métricas */
const STORAGE_KEY = "leilao.historico.v6";
const STORE_KEY = "historico.v6";

/** Teto de execuções guardadas */
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

/** Os nomes de antes de 04/11/2026, quando "utilidade" se partiu em duas palavras: **interesse** é o sorteio normalizado, que σ e a estabilidade governam e que o histograma retrata; **utilidade** é ele visto pelo histórico do aluno */
const INTEREST_RENAMES = [
  ["utility_sigma", "interest_sigma"],
  ["utility_stability", "interest_stability"],
  ["utility_distribution", "interest_distribution"],
] as const;

/** Troca as chaves antigas pelas de `INTEREST_RENAMES` */
export function withInterestNames<T extends object>(record: T): T {
  const migrated = { ...record } as Record<string, unknown>;
  for (const [old, current] of INTEREST_RENAMES) {
    if (!(old in migrated)) continue;
    if (migrated[current] === undefined) migrated[current] = migrated[old];
    delete migrated[old];
  }
  return migrated as T;
}

/** Os campos de interesse de um **cenário** gravado antes de 04/11/2026: as chaves novas (`withInterestNames`) e o μ, que não existia */
export function migrateInterest<T extends object>(config: T): T {
  const migrated = withInterestNames(config) as Record<string, unknown>;
  if (typeof migrated.interest_mean !== "number") migrated.interest_mean = 0;
  return migrated as T;
}

/** O cenário de uma execução gravada antes de 31/10/2026, traduzido para os campos de hoje */
function migrateScenario<T extends Record<string, unknown>>(config: T): T {
  const migrated = migrateInterest(config);
  const campos = migrated as Record<string, unknown>;
  if (typeof campos.min_credits !== "number") {
    campos.min_credits =
      typeof campos.base_credits === "number" ? campos.base_credits : 12;
    delete campos.base_credits;
  }
  delete campos.return_multiplier;
  delete campos.exclusion_refund_rate;
  if (typeof campos.slots !== "number") {
    const dia = typeof campos.day_slots === "number" ? campos.day_slots : 12;
    const noite = typeof campos.night_slots === "number" ? campos.night_slots : 6;
    campos.slots = dia + noite;
  }
  delete campos.day_slots;
  delete campos.night_slots;
  delete campos.routine_profiles;
  delete campos.class_difficulty_levels;
  if (typeof campos.observation_periods !== "number") {
    const entradas =
      typeof campos.entry_periods === "number" ? campos.entry_periods : 8;
    campos.observation_periods = Math.max(1, entradas);
  }
  delete campos.entry_periods;
  if (typeof campos.students_per_entry_class !== "number") {
    campos.students_per_entry_class = defaultScenario().students_per_entry_class;
  }
  delete campos.students_per_period;
  return migrated;
}

/** Grade legada ainda pode trazer `prerequisites` no lugar de `unlocks`; o resto do cenário legado passa por `migrateScenario` */
const migrateEntry = <T extends HistoryEntry>(entry: T): T =>
  ({
    ...entry,
    config: migrateScenario({
      ...entry.config,
      disciplines: withUnlocks(entry.config.disciplines ?? []),
    }),
    result: withInterestNames(entry.result),
  }) as T;

/** O histórico do `localStorage`, de antes do IndexedDB */
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
  }
}

/** Lê o histórico */
let loading: Promise<HistoryEntry[]> | null = null;

export function loadHistory(): Promise<HistoryEntry[]> {
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

/** Grava o histórico, podado a `MAX_RUNS` */
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

/** Uma execução gravada em disco pela API, de volta para a lista */
export function entryFromFile(text: string): HistoryEntry {
  const parsed = JSON.parse(text);
  if (parsed?.kind !== "comparison") {
    throw new Error("arquivo não é uma comparação do simulador");
  }
  if (!parsed.config || !parsed.result) {
    throw new Error("arquivo sem cenário ou sem resultado");
  }
  if (!Array.isArray(parsed.config.selectivity_profiles)) {
    throw new Error(
      "arquivo de antes dos eixos de estratégia e das turmas — não há como convertê-lo"
    );
  }
  return {
    ...parsed,
    ...stamp(),
    at: typeof parsed.at === "string" ? parsed.at : new Date().toISOString(),
    config: migrateScenario({
      ...parsed.config,
      disciplines: withUnlocks(parsed.config.disciplines ?? []),
    }),
    result: withInterestNames(parsed.result),
  } as HistoryEntry;
}

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

function describeScenario(config: Scenario | CompareRequest): string {
  const { rounds, disciplines } = config;
  const periods = horizonFor(config.max_residence);
  const students =
    cohortSize(config.students_per_entry_class, entryClasses(disciplines)) *
    config.max_residence;
  const rodadas = rounds === 1 ? "1 rodada" : `${rounds} rodadas`;
  const horizonte =
    config.max_residence > 0
      ? `${periods} períodos (${config.max_residence} de pré-população, ${config.max_residence} medidos)`
      : `${periods} períodos`;
  const numero = (value: number) => value.toLocaleString("pt-BR");
  const populacao = [
    `aprova ${numero(Math.round(config.approval_rate * 100))}%`,
    `carga ${numero(config.availability.mode_hours)} h`,
    `seletividade ${config.selectivity_median.toLocaleString("pt-BR", {
      maximumFractionDigits: 5,
    })}`,
    `interesse σ ${numero(config.interest_sigma)}`,
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
  const arms = run.config.arms?.length ?? COMPARISON_ARMS.length;
  return `${run.config.runs} seeds × ${arms} ${
    arms === 1 ? "modelo" : "modelos"
  } · ${describeScenario(run.config)}`;
}

export const describeEntry = (entry: HistoryEntry): string =>
  describeComparison(entry);
