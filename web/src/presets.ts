import type { DisciplineInput, SimulateRequest } from "./types";

/** Um cenário pronto. `hint` diz para que ele serve — a lista existe para
 * poupar a montagem manual de cenários que se repetem na pesquisa. */
export interface Preset {
  id: string;
  name: string;
  hint: string;
  build: () => SimulateRequest;
}

/** As seis combinações de oferta que se repetem a partir do 2º período: três
 * tamanhos de turma × duas cargas horárias.
 *
 * Essa regularidade é o que torna os gráficos por disciplina legíveis. Do 2º
 * período em diante, agrupar por carga horária dá duas séries com 15
 * disciplinas cada e agrupar por período dá cinco com 6 — e em qualquer um dos
 * recortes os outros eixos estão igualmente distribuídos dentro de cada grupo.
 * Então uma diferença entre séries é da grandeza em tela, não de um
 * desequilíbrio de composição.
 *
 * As 40 vagas são o gargalo do cenário e as de 120 nunca apertam; é essa
 * gradação que o recorte por vagas mede. O **1º período é a exceção**: ali tudo
 * tem 120 vagas, porque a geração inteira entra de uma vez por matrícula
 * garantida e ainda precisa sobrar lugar para quem recursa. Isso desequilibra o
 * recorte por vagas (o grupo de 120 fica com 16 disciplinas contra 10 dos
 * outros dois), e é de propósito: a alternativa seria um 1º período que
 * estrangula a entrada antes de o mecanismo ter o que alocar. */
const SEATS = [40, 80, 120] as const;
const ENTRY_SEATS = 120;
const HOURS = [60, 90] as const;

/** [nome, carga horária (w_x), vagas (q_x), predecessores na autoria].
 *
 * A lista final da tupla é só para escrever a grade: "esta depende destas".
 * `toDisciplines` inverte isso em `unlocks` (sucessores), que é o que o motor
 * e a API guardam. O período da grade sai da aresta inversa; a altura \(s_x\),
 * da lista de sucessores (`curriculum.ts`).
 *
 * Cada período soma 450 h no Computação (390 no Homogêneo), que é o W_a do
 * preset: o aluno em dia cursa as seis do seu período e nada mais. */
type Entry = [string, number, number, string[]];

const P1: Entry[] = [
  ["Cálculo I", 90, ENTRY_SEATS, []],
  ["Programação I", 90, ENTRY_SEATS, []],
  ["Matemática Discreta", 90, ENTRY_SEATS, []],
  ["Geometria Analítica", 60, ENTRY_SEATS, []],
  ["Laboratório de Programação", 60, ENTRY_SEATS, []],
  ["Introdução à Computação", 60, ENTRY_SEATS, []],
];

const P2: Entry[] = [
  ["Cálculo II", 90, 40, ["Cálculo I"]],
  ["Estruturas de Dados", 90, 80, ["Programação I", "Matemática Discreta"]],
  ["Álgebra Linear", 90, 120, ["Geometria Analítica"]],
  ["Circuitos Digitais", 60, 40, ["Introdução à Computação"]],
  ["Programação II", 60, 80, ["Programação I"]],
  ["Laboratório de Programação II", 60, 120, ["Laboratório de Programação"]],
];

const P3: Entry[] = [
  ["Algoritmos", 90, 40, ["Estruturas de Dados"]],
  ["Arquitetura de Computadores", 90, 80, ["Circuitos Digitais"]],
  ["Cálculo Numérico", 90, 120, ["Cálculo II", "Álgebra Linear"]],
  ["Banco de Dados", 60, 40, ["Estruturas de Dados"]],
  ["Paradigmas de Programação", 60, 80, ["Programação II"]],
  ["Probabilidade e Estatística", 60, 120, ["Cálculo II"]],
];

const P4: Entry[] = [
  ["Teoria da Computação", 90, 40, ["Algoritmos"]],
  ["Sistemas Operacionais", 90, 80, ["Arquitetura de Computadores"]],
  ["Inteligência Artificial", 90, 120, ["Algoritmos", "Probabilidade e Estatística"]],
  ["Redes de Computadores", 60, 40, ["Arquitetura de Computadores"]],
  ["Engenharia de Software", 60, 80, ["Banco de Dados", "Paradigmas de Programação"]],
  ["Computação Gráfica", 60, 120, ["Cálculo Numérico", "Paradigmas de Programação"]],
];

const P5: Entry[] = [
  ["Compiladores", 90, 40, ["Teoria da Computação"]],
  ["Sistemas Distribuídos", 90, 80, ["Sistemas Operacionais", "Redes de Computadores"]],
  ["Aprendizado de Máquina", 90, 120, ["Inteligência Artificial"]],
  ["Segurança Computacional", 60, 40, ["Redes de Computadores"]],
  ["Qualidade e Teste de Software", 60, 80, ["Engenharia de Software"]],
  ["Projeto de Pesquisa", 60, 120, ["Engenharia de Software", "Probabilidade e Estatística"]],
];

const P6: Entry[] = [
  ["Trabalho de Conclusão de Curso", 90, 40, ["Projeto de Pesquisa"]],
  ["Processamento de Linguagem Natural", 90, 80, ["Aprendizado de Máquina"]],
  ["Computação em Nuvem", 90, 120, ["Sistemas Distribuídos"]],
  ["Otimização de Código", 60, 40, ["Compiladores"]],
  ["Criptografia Aplicada", 60, 80, ["Segurança Computacional"]],
  ["Gerência de Projetos de Software", 60, 120, ["Qualidade e Teste de Software"]],
];

const GRADE = [P1, P2, P3, P4, P5, P6];

/** Vagas do preset Homogêneo, uma por período, iguais para todas as disciplinas
 * daquele período. O 1º ainda comporta a geração inteira e sobra lugar para
 * quem recursa. Dali em diante a oferta cai 15 vagas por período e a
 * concorrência aperta em funil: no 6º cabem menos da metade dos ingressantes. */
const FUNNEL_SEATS = [120, 105, 90, 75, 60, 45] as const;

/** Carga do Homogêneo, na ordem em que cada período está listado na grade.
 * As três de 60 h permanecem; das três de 90 h, a última de cada período vira
 * 30 h. A soma do período cai de 450 para 390. */
const FUNNEL_HOURS = [90, 90, 30, 60, 60, 60] as const;

const withFunnelOffer = (groups: Entry[][]): Entry[][] =>
  groups.map((period, index) =>
    period.map(
      ([name, , , dependsOn], slot): Entry => [
        name,
        FUNNEL_HOURS[slot],
        FUNNEL_SEATS[index],
        dependsOn,
      ],
    ),
  );

const FUNNEL_GRADE = withFunnelOffer(GRADE);

/** Carga horária máxima por período (W_a). É a soma de um período da grade de
 * cada preset: quem está em dia cursa as seis disciplinas do seu período e
 * nada mais. */
const MAX_HOURS = HOURS.reduce((sum, h) => sum + h * SEATS.length, 0); // 450
const FUNNEL_MAX_HOURS = FUNNEL_HOURS.reduce((sum, h) => sum + h, 0); // 390

/** Alunos que ingressam por período. O teto formal é a menor oferta de 1º
 * período (120), mas quem dimensiona o cenário é o gargalo seguinte: as
 * disciplinas de 40 vagas, que a partir do 2º período servem toda a população
 * em dia. Acima disso a fila nelas cresce sem nunca drenar e ninguém chega ao
 * fim da grade; bem abaixo, nada aperta e não há escassez a alocar.
 *
 * Calibrado rodando o cenário, e revalidado em σ = 1: 29% concluem em 12
 * períodos, a conclusão mais rápida em 7 — um acima do piso da cadeia, porque
 * com a utilidade resorteada por período ninguém quer exatamente as seis do seu
 * período semestre após semestre. O recorte por vagas fica legível: as de 40
 * são o gargalo e as de 120 nunca apertam. Com 30 a universidade fica frouxa
 * (ψ̄ perto de 1); com 70 a conclusão despenca. Como os números andam com σ, é a
 * varredura que os põe em contexto. */
const STUDENTS_PER_PERIOD = 60;

/** Ingressantes por período no Homogêneo. Cabem nas 120 vagas do 1º período e
 * já empatam com a oferta do 2º: quem reprova ou recursa disputa vaga com a
 * geração seguinte, e do 3º em diante a oferta é menor que a turma ingressante. */
const FUNNEL_STUDENTS_PER_PERIOD = 105;

/** Os alunos do cenário Computação. **Não há perfis**: estas são as duas
 * normais de que toda a população sai, e o que distingue um aluno do outro é só
 * o que a seed sorteou para ele.
 *
 * A normal das notas é a do perfil "Regular" que existia até 08/10/2026 — e,
 * não por acaso, a média da mistura dos três perfis de então (0,25·8 + 0,50·6,5
 * + 0,25·5 = 6,5). O desvio é menor que o da mistura, porque ali parte da
 * dispersão vinha da distância *entre* os perfis, e essa é justamente a
 * diferença sistemática que saiu.
 *
 * O desvio da utilidade é o default do modelo, sigma = 1: o meio da faixa útil
 * (~0,25 a ~3), em que o aluno diferencia as disciplinas de forma clara sem
 * virar fanático — o meio do caminho entre os perfis "Focados" e "Dispersos"
 * que havia antes. É o valor **canônico**, o que os boxplots medem; a varredura
 * passa por ele e o marca no eixo. */
const POPULATION = {
  grade_mean: 6,
  grade_stddev: 1,
  learning_gain: 0.5,
  utility_sigma: 1,
  max_hours: MAX_HOURS,
};

/** Os alunos do cenário Homogêneo: as mesmas duas normais, bem mais apertadas.
 *
 * O preset existia para controlar a **heterogeneidade dos perfis**, e os perfis
 * saíram — mas o controle continua fazendo sentido, só que agora é um controle
 * de *dispersão*, que é o que restou do mesmo conceito. Com as notas quase
 * iguais o CR tem pouco a ordenar, e com sigma = 0,25 as utilidades ficam quase
 * uniformes (a preferida vale ~1,9x a menos querida), então o leilão tem pouca
 * preferência a captar: o que a comparação mostrar aqui é da regra de alocação,
 * não de quem a população é. */
const FLAT_POPULATION = {
  grade_mean: 6,
  grade_stddev: 1,
  learning_gain: 0.5,
  utility_sigma: 0.25,
  max_hours: FUNNEL_MAX_HOURS,
};

/** Inverte a autoria por predecessores na lista de sucessores do motor. */
const toDisciplines = (groups: Entry[][]): DisciplineInput[] => {
  const flat = groups.flat();
  const unlocks = new Map<string, string[]>(flat.map(([name]) => [name, []]));
  for (const [name, , , dependsOn] of flat) {
    for (const predecessor of dependsOn) {
      unlocks.get(predecessor)?.push(name);
    }
  }
  return flat.map(([name, hours, seats]) => ({
    name,
    hours,
    seats,
    unlocks: unlocks.get(name) ?? [],
  }));
};

/** Horizonte, rodadas e seed que os dois presets compartilham. A oferta e o
 * tamanho da geração entram por argumento: o Computação varia vagas dentro do
 * período, o Homogêneo iguala as vagas e afunila a oferta. */
const commonScenario = (
  disciplines: DisciplineInput[],
  studentsPerPeriod: number,
): Omit<
  SimulateRequest,
  "grade_mean" | "grade_stddev" | "learning_gain" | "utility_sigma" | "max_hours" | "base_credits"
> => ({
  disciplines,
  periods: 12,
  // Ingresso nos 6 primeiros e drenagem nos 6 últimos. Sem a drenagem as
  // últimas gerações eram cortadas pelo horizonte antes de poderem se formar —
  // a última geração vivia um período só —, e a série por geração media quanto
  // tempo de simulação sobrou, não o mecanismo. Seis é o piso teórico da grade:
  // a cadeia de pré-requisitos tem seis elos, então ninguém conclui em menos
  // que isso nem no melhor dos casos.
  entry_periods: 6,
  students_per_period: studentsPerPeriod,
  rounds: 2,
  min_grade: 5,
  credit_return: "none",
  seed: 42,
});

export const PRESETS: Preset[] = [
  {
    id: "computacao",
    name: "Computação",
    hint: "Grade de 6 períodos com 6 disciplinas cada, encadeadas por pré-requisitos; do 2º período em diante repetem-se as combinações de 40/80/120 vagas × 60/90 h. 60 ingressantes por período em 6 períodos, 360 alunos, e mais 6 períodos de drenagem.",
    build: (): SimulateRequest => ({
      ...commonScenario(toDisciplines(GRADE), STUDENTS_PER_PERIOD),
      ...POPULATION,
      base_credits: 10,
    }),
  },
  {
    id: "homogeneo",
    name: "Homogêneo",
    hint: "Mesma grade e mesmas normais apertadas, com oferta em funil: todas as disciplinas de um período têm as mesmas vagas (120, 105, 90, 75, 60 e 45 do 1º ao 6º) e entram 105 alunos por período. Cada período tem 2 disciplinas de 90 h, 3 de 60 h e 1 de 30 h (W_a = 390). Γ_min = 12. A concorrência aperta a cada período; com alunos quase idênticos, o que a comparação mostrar é da regra de alocação.",
    // Existe para a comparação entre mecanismos. No Computação, parte do vão
    // entre CR e créditos pode vir de como cada um trata uma população
    // dispersa: a ordenação por CR premia quem tira nota alta por construção, e
    // o leilão rende mais a quem concentra a preferência. Aqui quase não há a
    // quem premiar.
    //
    // Até 08/10/2026 este preset era o controle da **heterogeneidade dos
    // perfis**; com os perfis fora do modelo, ele passou a ser o controle da
    // **dispersão**, que é o que restou do mesmo conceito. A oferta deixou de
    // ser a do Computação: as vagas são iguais dentro do período e caem em
    // funil, e a geração (105) já empata com o 2º período.
    build: (): SimulateRequest => ({
      ...commonScenario(toDisciplines(FUNNEL_GRADE), FUNNEL_STUDENTS_PER_PERIOD),
      ...FLAT_POPULATION,
      base_credits: 12,
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
