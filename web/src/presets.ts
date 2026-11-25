import type { SavedPreset } from "./savedPresets";
import type { DisciplineInput, Scenario } from "./types";

/** A população: os quatro eixos de perfil mais o sigma do interesse */
const POPULATION: Pick<
  Scenario,
  | "approval_rate"
  | "grade_sd"
  | "repetition_gain"
  | "availability"
  | "availability_fluctuation"
  | "selectivity_mean"
  | "selectivity_sigma"
  | "selectivity_fluctuation"
  | "schedule_mean"
  | "schedule_sigma"
  | "schedule_fluctuation"
  | "grade_cuts"
  | "reserve_cuts"
  | "interest_mean"
  | "interest_sigma"
  | "interest_fluctuation"
> = {
  approval_rate: 0.7,
  grade_sd: 2,
  repetition_gain: 1,
  availability: { hours_sd: 1.2, full_load_rate: 0.05 },
  availability_fluctuation: 0.5,
  selectivity_mean: 0.7,
  selectivity_sigma: 0.6,
  selectivity_fluctuation: 0,
  schedule_mean: 0,
  schedule_sigma: 0.6,
  schedule_fluctuation: 0.25,
  grade_cuts: [5, 7],
  reserve_cuts: [0.01, 0.03],
  interest_mean: 1,
  interest_sigma: 1,
  interest_fluctuation: 0.25,
};

/** Os eixos da população que um cenário salvo antes deles pode não trazer */
export const strategyDefaults = () => ({ ...POPULATION });


/** **A grade: o funil.** Seis níveis de seis obrigatórias, mais 24 optativas */
const LEVEL_HOURS = [1, 2, 3, 4, 5, 6];
const LEVELS = 6;

/** O **funil**: turmas por disciplina, nível a nível */
const CLASSES_BY_LEVEL = [10, 9, 8, 7, 6, 5];

/** Alunos por turma do cenário padrão */
export const DEFAULT_CLASS_SIZE = 50;

const requiredName = (level: number, suffix: number) =>
  `Obrigatória ${level}.${suffix}`;

/** **O sufixo é a carga.** `Obrigatória k.3` tem 3 h em qualquer nível k, e a `Optativa g.3` também */
const shiftSuffix = (suffix: number, by: number) =>
  ((suffix - 1 + by) % LEVEL_HOURS.length) + 1;

const FACTORIAL_REQUIRED: DisciplineInput[] = Array.from(
  { length: LEVELS * LEVEL_HOURS.length },
  (_, index) => {
    const level = Math.floor(index / LEVEL_HOURS.length) + 1;
    const suffix = (index % LEVEL_HOURS.length) + 1;
    return {
      name: requiredName(level, suffix),
      hours: LEVEL_HOURS[suffix - 1],
      classes: CLASSES_BY_LEVEL[level - 1],
      unlocks:
        level < LEVELS
          ? [
              requiredName(level + 1, shiftSuffix(suffix, 1)),
              requiredName(level + 1, shiftSuffix(suffix, 2)),
            ]
          : [],
      entry: level === 1,
    };
  },
);

/** As 24 optativas: quatro grupos de seis, cada grupo um patamar de oferta cruzado com as seis cargas */
const ELECTIVE_CLASSES = [1, 2, 3, 4];

const FACTORIAL_ELECTIVES: DisciplineInput[] = ELECTIVE_CLASSES.flatMap(
  (classes, group) =>
    LEVEL_HOURS.map((hours, index) => ({
      name: `Optativa ${group + 1}.${index + 1}`,
      hours,
      classes,
      unlocks: [] as string[],
      entry: false,
      elective: true,
    })),
);

/** W_a = 24 h, contra as 21 que o 1º nível oferece (1+2+3+4+5+6) */
const FACTORIAL_MAX_HOURS = 24;

/** X — exigência optativa, contra 84 h ofertadas no catálogo (quatro grupos de 1+2+3+4+5+6 h) */
const FACTORIAL_ELECTIVE_HOURS = 24;

/** Ingressantes em cada turma de disciplina de entrada */
const FACTORIAL_ENTRANTS_PER_CLASS = 15;

/** **A grade, única para todo o aplicativo.** A oferta não é parâmetro de cenário: o formulário não a edita, e quem a mostra é a tela Grade */
export const GRADE: DisciplineInput[] = [...FACTORIAL_REQUIRED, ...FACTORIAL_ELECTIVES];

/** **Os valores padrão do formulário**: o cenário que a tela abre antes de qualquer escolha */
export const defaultScenario = (): Scenario => ({
  disciplines: GRADE,
  class_size: DEFAULT_CLASS_SIZE,
  students_per_entry_class: FACTORIAL_ENTRANTS_PER_CLASS,
  elective_hours: FACTORIAL_ELECTIVE_HOURS,
  max_hours: FACTORIAL_MAX_HOURS,
  max_residence: 20,
  first_seed: 1,
  rounds: 3,
  min_grade: 5,
  slots: 11,
  seed: 42,
  ...POPULATION,
  min_credits: 12,
  max_credits: 30,
});

/** Estado da escolha de cenário na tela de configuração */
export interface PresetChoice {
  config: Scenario;
  presetId: string | null;
  custom: Scenario | null;
}

export const initialChoice = (): PresetChoice => ({
  config: defaultScenario(),
  presetId: null,
  custom: null,
});

/** Clique na lista: carrega um cenário salvo, ou volta ao personalizado — que é o que o usuário montou ou, enquanto não montou nada, o padrão */
export function choosePreset(
  choice: PresetChoice,
  id: string | null,
  saved: SavedPreset[] = []
): PresetChoice {
  if (id === choice.presetId) return choice;
  if (id === null) {
    return { ...choice, config: choice.custom ?? defaultScenario(), presetId: null };
  }
  const stored = saved.find((p) => p.id === id);
  return stored
    ? { ...choice, config: { ...stored.config, disciplines: GRADE }, presetId: id }
    : choice;
}

export function editConfig(_choice: PresetChoice, config: Scenario): PresetChoice {
  return { config, presetId: null, custom: config };
}
