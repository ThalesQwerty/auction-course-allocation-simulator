import { entryClasses, withUnlocks } from "./curriculum";
import { cohortSize } from "./equations";
import { defaultScenario } from "./presets";
import { COMPARISON_ARMS, horizonFor } from "./types";
import type {
  CompareRequest,
  CompareResponse,
  SavedResult,
  Scenario,
  StoredRun,
} from "./types";

/** Uma execução da lista: o que a API devolve sem o resultado, que é o que a barra lateral precisa */
export interface HistoryEntry {
  kind: "comparison";
   /** O nome em disco, que endereça `/results/{id}` */
  id: string;
  at: string; // ISO 8601
  config: CompareRequest;
  bytes?: number;
}

/** Uma execução aberta: a da lista, com o resultado */
export interface ComparisonRun extends HistoryEntry {
  result: CompareResponse;
}

/** Os nomes de antes de 04/11/2026, quando "utilidade" se partiu em duas palavras: **interesse** é o sorteio que σ e a flutuação governam e que o histograma retrata; **utilidade** é ele visto pelo histórico do aluno */
const INTEREST_RENAMES = [
  ["utility_sigma", "interest_sigma"],
  ["utility_distribution", "interest_distribution"],
] as const;

/** Chaves que saíram do cenário. A estabilidade não se converte em flutuação: uma era o quanto da âncora permanecia, a outra é o desvio do abalo */
const RETIRED_KEYS = [
  "selectivity_median",
  "utility_stability",
  "interest_stability",
  "availability_stability",
];

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
  for (const key of RETIRED_KEYS) delete migrated[key];
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

/** Uma linha da lista da API, traduzida para a barra lateral */
export function entryFromListing(row: SavedResult): HistoryEntry {
  return {
    kind: "comparison",
    id: row.name,
    at: row.at,
    bytes: row.bytes,
    config: migrateConfig(row.config),
  };
}

/** Uma execução gravada, traduzida para a tela de resultados */
export function runFromStored(name: string, stored: StoredRun): ComparisonRun {
  return {
    kind: "comparison",
    id: name,
    at: stored.at,
    config: migrateConfig(stored.config),
    result: migrateResult(withInterestNames(stored.result)),
  };
}

/** A chave de ψ̄ antes de 25/11/2026, quando ela ainda se chamava pela eq. (53) do anteprojeto e não pelo que mede */
const SATISFACTION_WAS = "efficiency";

/** Troca a chave de ψ̄ onde ela estiver: ela aparece no resumo de cada simulação, nos valores de cada faixa e em cada ponto da dispersão */
function migrateResult(result: CompareResponse): CompareResponse {
  const probe = result.arms?.[0]?.runs?.[0] as unknown as
    | Record<string, unknown>
    | undefined;
  if (!probe || !(SATISFACTION_WAS in probe)) return result;
  return renameDeep(result) as CompareResponse;
}

function renameDeep(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(renameDeep);
  if (value === null || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, inner]) => [
      key === SATISFACTION_WAS ? "satisfaction" : key,
      renameDeep(inner),
    ])
  );
}

/** O cenário gravado, nos campos de hoje */
function migrateConfig(config: CompareRequest): CompareRequest {
  return migrateScenario({
    ...config,
    disciplines: withUnlocks(config.disciplines ?? []),
  });
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

const numero = (value: number) => value.toLocaleString("pt-BR");

/** Escreve a parte só se o cenário gravado trouxer o campo: execução antiga não tem todos, e inventar número seria relatar o que não rodou */
const se = (
  value: number | undefined,
  write: (value: number) => string
): string | null => (typeof value === "number" ? write(value) : null);

function describeScenario(config: Scenario | CompareRequest): string {
  const { rounds, disciplines } = config;
  const partes = [
    se(config.max_residence, (residencia) =>
      residencia > 0
        ? `${horizonFor(residencia)} períodos (${residencia} de pré-população, ${residencia} medidos)`
        : `${horizonFor(residencia)} períodos`
    ),
    se(rounds, (value) => (value === 1 ? "1 rodada" : `${value} rodadas`)),
  ].filter((parte): parte is string => parte !== null);

  const populacao = [
    `${disciplines?.length ?? 0} disciplinas`,
    se(
      config.students_per_entry_class !== undefined && config.max_residence
        ? cohortSize(config.students_per_entry_class, entryClasses(disciplines)) *
            config.max_residence
        : undefined,
      (value) => `${value} alunos`
    ),
    se(config.approval_rate, (value) => `aprova ${numero(Math.round(value * 100))}%`),
    se(config.availability?.hours_sd, (value) => `carga σ ${numero(value)} h`),
    se(
      config.selectivity_mean,
      (value) =>
        `seletividade ${value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}`
    ),
    se(config.interest_sigma, (value) => `interesse σ ${numero(value)}`),
  ].filter((parte): parte is string => parte !== null);

  return `${partes.join(" × ")} · ${populacao.join(" · ")}`;
}

export function describeComparison(run: HistoryEntry): string {
  const arms = run.config.arms?.length ?? COMPARISON_ARMS.length;
  return `${run.config.runs} seeds × ${arms} ${
    arms === 1 ? "modelo" : "modelos"
  } · ${describeScenario(run.config)}`;
}

export const describeEntry = describeComparison;
