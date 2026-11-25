/** Cenários que o usuário salva no navegador, ao lado dos prontos */
import { migrateInterest } from "./history";
import { entryClasses } from "./curriculum";
import { cohortSize } from "./equations";
import { GRADE, strategyDefaults } from "./presets";
import { horizonFor } from "./types";
import type { Scenario } from "./types";

/** O que um cenário salvo guarda: tudo **menos a grade** */
export type SavedScenario = Omit<Scenario, "disciplines">;

export interface SavedPreset {
  id: string;
   /** O nome que o usuário deu, e a **identidade** do cenário: salvar com um nome que já existe sobrescreve aquele, em vez de criar um segundo com o mesmo rótulo */
  name: string;
  at: string; // ISO 8601
  config: SavedScenario;
}

/** A versão entra na chave pelo mesmo motivo do histórico: um cenário salvo antes dos perfis não tem como ser convertido — a Beta única virou duas listas de grupos, e a disponibilidade não existia */
const STORAGE_KEY = "leilao.cenarios.v2";

/** Teto de cenários guardados */
export const MAX_SAVED = 30;

function withStrategy(config: Scenario): Scenario {
  return { ...strategyDefaults(), ...config };
}

export function loadSavedPresets(): SavedPreset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return (parsed as SavedPreset[])
      .filter((entry) => entry && typeof entry.id === "string" && entry.config)
      .map((entry) => ({
        ...entry,
        config: withoutGrade(withStrategy(migrateInterest(entry.config as Scenario))),
      }));
  } catch {
    return [];
  }
}

/** Grava a lista, descartando os mais antigos enquanto o navegador recusar por falta de espaço */
export function saveSavedPresets(entries: SavedPreset[]): SavedPreset[] {
  let kept = entries.slice(0, MAX_SAVED);
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
  }
  return [];
}

/** Comparação de nomes: sem espaços nas pontas e sem distinguir maiúsculas */
const sameName = (a: string, b: string) =>
  a.trim().localeCompare(b.trim(), "pt-BR", { sensitivity: "base" }) === 0;

export const nameExists = (entries: SavedPreset[], name: string): boolean =>
  entries.some((entry) => sameName(entry.name, name));

/** Salva o cenário sob `name`, **substituindo** o que já tiver esse nome */
export function upsertSavedPreset(
  entries: SavedPreset[],
  name: string,
  config: Scenario
): SavedPreset[] {
  const existing = entries.find((entry) => sameName(entry.name, name));
  const saved: SavedPreset = {
    id: existing?.id ?? `salvo-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: name.trim(),
    at: new Date().toISOString(),
    config: withoutGrade(config),
  };
  return [saved, ...entries.filter((entry) => entry.id !== saved.id)];
}

/** Tira a grade do que vai para o disco */
const withoutGrade = (config: Scenario): SavedScenario => {
  const { disciplines: _grade, ...rest } = config;
  return rest;
};

/** O que distingue um cenário salvo de outro */
export const describeSaved = (preset: SavedPreset): string => {
  const cohort = cohortSize(
    preset.config.students_per_entry_class,
    entryClasses(GRADE)
  );
  const students = cohort * preset.config.max_residence;
  const periods = horizonFor(preset.config.max_residence);
  return (
    `${students} alunos · ${periods} períodos · ` +
    `salvo em ${formatSavedDate(preset.at)}`
  );
};

export const formatSavedDate = (iso: string): string => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
};
