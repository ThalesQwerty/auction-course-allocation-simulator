/** Cenários que o usuário salva no navegador, ao lado dos prontos.
 *
 * Mesma ideia do histórico de execuções — `localStorage`, sem servidor —, mas
 * guarda **entrada** e não resultado: um cenário salvo é o formulário inteiro,
 * e carregá-lo repõe exatamente o que estava ali. Por isso cabe muito mais
 * coisa aqui do que lá: um cenário são uns poucos kB, enquanto uma execução
 * carrega todas as séries de todos os braços.
 *
 * A chave é separada da do histórico de propósito. Limpar execuções não apaga
 * cenários, e um formato que mude de um lado não derruba o outro.
 */
import { cohortSize } from "./equations";
import { migrateInterest } from "./history";
import { horizonFor } from "./types";
import type { Scenario } from "./types";

/** O que um cenário salvo guarda: tudo **menos a grade**.
 *
 * A oferta não é parâmetro de cenário — o formulário não a edita, e ela é a
 * mesma para todos os presets. Guardar uma cópia aqui seria guardar algo que
 * pode divergir da única que existe; quem recarrega um salvo pega a grade
 * corrente, que é o que "a grade é a mesma para todos" quer dizer. */
export type SavedScenario = Omit<Scenario, "disciplines">;

export interface SavedPreset {
  id: string;
  /** O nome que o usuário deu, e a **identidade** do cenário: salvar com um
   * nome que já existe sobrescreve aquele, em vez de criar um segundo com o
   * mesmo rótulo. É o que torna "salvar de novo" a forma natural de editar um
   * cenário salvo, sem precisar de um modo de edição à parte. */
  name: string;
  at: string; // ISO 8601
  config: SavedScenario;
}

/** A versão entra na chave pelo mesmo motivo do histórico: um cenário salvo
 * antes dos perfis não tem como ser convertido — a Beta única virou duas
 * listas de grupos, e a disponibilidade não existia. Em vez de carregar meio
 * vazio, a v1 simplesmente não lê o que veio antes dela. */
const STORAGE_KEY = "leilao.cenarios.v2";

/** Teto de cenários guardados. Não é limitação de espaço — cada um é pequeno —,
 * é que uma lista maior que isso deixa de se escolher de relance. */
export const MAX_SAVED = 30;

export function loadSavedPresets(): SavedPreset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return (parsed as SavedPreset[])
      .filter((entry) => entry && typeof entry.id === "string" && entry.config)
      .map((entry) => ({
        ...entry,
        // Salvo antes de 04/11/2026 traz `utility_sigma` e `utility_stability`,
        // e não traz `interest_mean`.
        config: withoutGrade(migrateInterest(entry.config as Scenario)),
      }));
  } catch {
    // localStorage indisponível (modo privado) ou conteúdo corrompido.
    return [];
  }
}

/** Grava a lista, descartando os mais antigos enquanto o navegador recusar por
 * falta de espaço. Devolve o que de fato coube — a tela mostra isso, em vez de
 * fingir que salvou. */
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
    // Nada a fazer: o navegador não guarda nada nesta sessão.
  }
  return [];
}

/** Comparação de nomes: sem espaços nas pontas e sem distinguir maiúsculas.
 * "Meu cenário" e "meu cenário" como duas entradas separadas seria confusão,
 * não liberdade. */
const sameName = (a: string, b: string) =>
  a.trim().localeCompare(b.trim(), "pt-BR", { sensitivity: "base" }) === 0;

export const nameExists = (entries: SavedPreset[], name: string): boolean =>
  entries.some((entry) => sameName(entry.name, name));

/** Salva o cenário sob `name`, **substituindo** o que já tiver esse nome.
 *
 * Na substituição o `id` é preservado: se aquele cenário estiver carregado no
 * formulário, ele continua sendo o selecionado na lista depois de gravado. O
 * grafado novo vence o antigo — quem redigitou "Meu Cenário" sobre "meu
 * cenário" quis a maiúscula —, e o atualizado sobe para o topo, que é onde se
 * procura o que se acabou de mexer.
 *
 * O id leva prefixo para nunca colidir com o de um preset pronto: a mesma
 * seleção endereça os dois.
 */
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

/** Tira a grade do que vai para o disco. Uma entrada gravada antes desta
 * regra traz `disciplines`, e descartá-la aqui é toda a migração necessária. */
const withoutGrade = (config: Scenario): SavedScenario => {
  const { disciplines: _grade, ...rest } = config;
  return rest;
};

/** O que distingue um cenário salvo de outro. A contagem de disciplinas não
 * entra: a grade é a mesma para todos, e repeti-la em toda linha não separaria
 * nada. */
export const describeSaved = (preset: SavedPreset): string => {
  const entries = preset.config.entry_periods;
  const students = cohortSize(preset.config) * entries;
  const periods = horizonFor(entries, preset.config.max_residence);
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
