import type { CourseInput, DisciplineInput, SimulateRequest } from "./types";

/** Um cenário pronto. `hint` diz para que ele serve — a lista existe para
 * poupar a montagem manual de cenários que se repetem na pesquisa. */
export interface Preset {
  id: string;
  name: string;
  hint: string;
  build: () => SimulateRequest;
}

/** [nome, carga horária (w_x), vagas (q_x)].
 *
 * As cargas horárias seguem a distribuição pedida: 60 h é a maioria; 45 h e
 * 75 h são a minoria; 30 h (laboratórios e disciplinas curtas) e 90 h (as
 * pesadas) ficam no meio.
 *
 * As vagas são escassas também no agregado: a oferta total fica muito abaixo
 * da carga horária que os alunos conseguiriam consumir, então o leilão raciona
 * em toda disciplina, não só nas obrigatórias disputadas por mais de um
 * curso. */
type Entry = [string, number, number];

/** Matemática básica — obrigatória nos três cursos. */
const BASIC_MATH: Entry[] = [
  ["Cálculo I", 90, 36],
  ["Cálculo II", 90, 30],
  ["Geometria Analítica", 60, 30],
  ["Álgebra Linear", 75, 30],
  ["Matemática Discreta", 60, 26],
];

/** Matemática intermediária — Matemática e Engenharia. */
const INTERMEDIATE_MATH: Entry[] = [
  ["Cálculo III", 60, 20],
  ["Equações Diferenciais", 60, 20],
  ["Probabilidade e Estatística", 60, 22],
  ["Cálculo Numérico", 45, 16],
];

/** Matemática avançada — só o curso de Matemática. */
const ADVANCED_MATH: Entry[] = [
  ["Análise Real", 90, 12],
  ["Álgebra Abstrata", 90, 12],
  ["Variáveis Complexas", 60, 10],
  ["Topologia", 60, 10],
];

/** Código — obrigatórias da Computação. */
const CODE: Entry[] = [
  ["Programação I", 60, 30],
  ["Programação II", 60, 24],
  ["Estrutura de Dados", 60, 22],
  ["Algoritmos", 60, 20],
  ["Banco de Dados", 60, 18],
  ["Sistemas Operacionais", 60, 18],
  ["Redes de Computadores", 60, 18],
  ["Engenharia de Software", 60, 18],
  ["Compiladores", 75, 14],
  ["Inteligência Artificial", 60, 16],
  ["Laboratório de Programação", 30, 20],
];

/** Física, eletrônica e hardware — obrigatórias da Engenharia. */
const HARDWARE: Entry[] = [
  ["Física I — Mecânica", 90, 26],
  ["Física II — Eletromagnetismo", 60, 24],
  ["Física III — Ondas e Termodinâmica", 60, 20],
  ["Circuitos Elétricos", 60, 20],
  ["Circuitos Digitais", 60, 20],
  ["Eletrônica Analógica", 75, 16],
  ["Arquitetura de Computadores", 60, 20],
  ["Microcontroladores", 45, 16],
  ["Sistemas Embarcados", 45, 14],
  ["Processamento de Sinais", 60, 14],
  ["Laboratório de Circuitos Digitais", 30, 18],
];

/** Disciplinas de serviço — optativas em todos os cursos. */
const GENERAL: Entry[] = [
  ["Metodologia Científica", 30, 24],
  ["Introdução à Engenharia", 30, 20],
  ["Economia", 60, 18],
];

const CATALOG = [
  ...BASIC_MATH, ...INTERMEDIATE_MATH, ...ADVANCED_MATH, ...CODE, ...HARDWARE, ...GENERAL,
];

const names = (...groups: Entry[][]) => groups.flat().map(([name]) => name);
const totalHours = (...groups: Entry[][]) => groups.flat().reduce((sum, [, w]) => sum + w, 0);

/** S_k tem de ficar entre a carga das obrigatórias e a das obrigatórias +
 * optativas — eq. (39). Exige-se as obrigatórias inteiras mais uma fração das
 * optativas, que é o que força o aluno a escolher entre elas. */
function course(
  name: string,
  studentsPerGeneration: number,
  required: Entry[][],
  electives: Entry[][],
  electiveShare: number
): CourseInput {
  const required_hours = totalHours(...required);
  const elective_hours = totalHours(...electives);
  return {
    name,
    students_per_generation: studentsPerGeneration,
    // arredondado para múltiplo de 15, que é o passo das cargas do catálogo
    hours_to_graduate: required_hours + Math.round((elective_hours * electiveShare) / 15) * 15,
    required: names(...required),
    electives: names(...electives),
  };
}

export const PRESETS: Preset[] = [
  {
    id: "campus",
    name: "Campus",
    hint: "Três cursos com grades que se cruzam; 150 ingressantes por período em 5 períodos, 750 alunos, e mais 5 períodos de drenagem.",
    build: (): SimulateRequest => ({
      disciplines: CATALOG.map(([name, hours, seats]): DisciplineInput => ({ name, hours, seats })),
      courses: [
        // Os números são por geração: com 5 períodos de ingresso dão 300, 200 e 250 alunos.
        // Matemática básica + código.
        course("Computação", 60, [BASIC_MATH, CODE], [INTERMEDIATE_MATH, HARDWARE, GENERAL], 0.2),
        // Toda a matemática.
        course("Matemática", 40, [BASIC_MATH, INTERMEDIATE_MATH, ADVANCED_MATH], [CODE, GENERAL], 0.2),
        // Física/eletrônica inteira + matemática até o nível intermediário.
        course("Engenharia", 50, [BASIC_MATH, INTERMEDIATE_MATH, HARDWARE], [CODE, GENERAL], 0.2),
      ],
      periods: 10,
      // Ingresso nos 5 primeiros e drenagem nos 5 últimos. Sem a drenagem as
      // últimas gerações eram cortadas pelo horizonte antes de poderem se
      // formar — a geração 10 vivia um período só —, e a série por geração
      // media quanto tempo de simulação sobrou, não o mecanismo.
      entry_periods: 5,
      // 0 = sem jubilamento. Este cenário é deliberadamente escasso (a oferta
      // fica muito abaixo do que os alunos consumiriam), e em 10 períodos só
      // ~6% concluem. Qualquer prazo aqui desligaria quase toda a população, o
      // que mede a calibragem do cenário e não o mecanismo. Para experimentar
      // o jubilamento, afrouxe a escassez ou alongue |T| antes.
      max_residence: 0,
      rounds: 2,
      min_grade: 5,
      base_credits: 10,
      max_hours: 360,
      learning_gain: 2.5,
      credit_return: "none",
      seed: 42,
    }),
  },
];

export const defaultPreset = PRESETS[0];

/** Estado da escolha de cenário na tela de configuração. `presetId` null
 * significa "Personalizado"; `custom` guarda o cenário montado à mão para que
 * experimentar um preset não o perca. */
export interface PresetChoice {
  config: SimulateRequest;
  presetId: string | null;
  custom: SimulateRequest | null;
}

export const initialChoice = (): PresetChoice => ({
  config: defaultPreset.build(),
  presetId: defaultPreset.id,
  custom: null,
});

/** Clique na lista: carrega o preset, ou volta ao cenário personalizado.
 * Clicar no que já está carregado não faz nada — inclusive não descarta o
 * cenário personalizado guardado. */
export function choosePreset(choice: PresetChoice, id: string | null): PresetChoice {
  if (id === choice.presetId) return choice;
  if (id === null) {
    return choice.custom ? { ...choice, config: choice.custom, presetId: null } : choice;
  }
  const preset = PRESETS.find((p) => p.id === id);
  return preset ? { ...choice, config: preset.build(), presetId: id } : choice;
}

/** Qualquer alteração no formulário passa a valer como cenário personalizado. */
export function editConfig(_choice: PresetChoice, config: SimulateRequest): PresetChoice {
  return { config, presetId: null, custom: config };
}
