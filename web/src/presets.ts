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

/** [nome, carga horária (w_x), vagas (q_x), pré-requisitos].
 *
 * O período de cada disciplina **não** é declarado: sai por indução dos
 * pré-requisitos (`curriculum.ts`). A grade abaixo está agrupada por período só
 * para ser legível — o que a põe no 3º período é cada uma delas depender de
 * alguma do 2º, não a posição na lista.
 *
 * Cada período soma 450 h, que é a carga horária máxima do cenário (W_a): o
 * aluno em dia cursa as seis disciplinas do seu período e
 * nada mais. Isso importa duas vezes. Faz a disputa ser por *quais* seis, e não
 * por quantas — quem fica para trás tem de escolher entre recuperar o atraso e
 * avançar. E deixa a matrícula garantida do ingressante caber em W_a: ele entra
 * nas seis do 1º período de uma vez, e a eq. (4) tem de continuar valendo. */
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

/** Carga horária máxima por período (W_a), igual para todos. É exatamente a
 * soma de um período da grade. */
const MAX_HOURS = HOURS.reduce((sum, h) => sum + h * SEATS.length, 0); // 450

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
  grade_mean: 6.5,
  grade_stddev: 1.5,
  learning_gain: 2.5,
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
  grade_stddev: 0.5,
  learning_gain: 2,
  utility_sigma: 0.25,
  max_hours: MAX_HOURS,
};

const toDisciplines = (groups: Entry[][]): DisciplineInput[] =>
  groups.flat().map(([name, hours, seats, prerequisites]) => ({
    name,
    hours,
    seats,
    prerequisites,
  }));

/** O que os dois presets têm em comum: a mesma universidade e a mesma
 * calibragem da oferta. Eles diferem só na dispersão das duas normais e em
 * Γ_min, que é justamente o que faz um servir de controle do outro — qualquer
 * diferença entre eles vem do que foi declarado na chamada, não da oferta. */
const commonScenario = (): Omit<
  SimulateRequest,
  "grade_mean" | "grade_stddev" | "learning_gain" | "utility_sigma" | "max_hours" | "base_credits"
> => ({
  disciplines: toDisciplines(GRADE),
  periods: 12,
  // Ingresso nos 6 primeiros e drenagem nos 6 últimos. Sem a drenagem as
  // últimas gerações eram cortadas pelo horizonte antes de poderem se formar —
  // a última geração vivia um período só —, e a série por geração media quanto
  // tempo de simulação sobrou, não o mecanismo. Seis é o piso teórico da grade:
  // a cadeia de pré-requisitos tem seis elos, então ninguém conclui em menos
  // que isso nem no melhor dos casos.
  entry_periods: 6,
  students_per_period: STUDENTS_PER_PERIOD,
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
      ...commonScenario(),
      ...POPULATION,
      base_credits: 10,
    }),
  },
  {
    id: "homogeneo",
    name: "Homogêneo",
    hint: "A mesma universidade do Computação, com as duas normais bem mais apertadas (notas 6 ± 0,5, utilidades σ 0,02) e Γ_min = 12. Serve de controle: com alunos quase idênticos, o CR tem pouco a ordenar e o leilão tem pouca preferência a captar, então o que a comparação mostrar é da regra de alocação.",
    // Existe para a comparação entre mecanismos. No Computação, parte do vão
    // entre CR e créditos pode vir de como cada um trata uma população
    // dispersa: a ordenação por CR premia quem tira nota alta por construção, e
    // o leilão rende mais a quem concentra a preferência. Aqui quase não há a
    // quem premiar.
    //
    // Até 08/10/2026 este preset era o controle da **heterogeneidade dos
    // perfis**; com os perfis fora do modelo, ele passou a ser o controle da
    // **dispersão**, que é o que restou do mesmo conceito.
    //
    // Rodado (N = 10), e o cenário não sai degenerado: ψ̄ 0,784 no CR contra
    // ~0,82 nos dois braços de crédito, φ 0,841 contra ~0,93, λ 0,628 contra
    // ~0,03. Com as notas quase iguais quase ninguém reprova, então forma-se
    // muito mais gente que no Computação (234 no CR contra 138) — é o preço de
    // ser um controle, e por isso ele não se lê como cenário realista.
    //
    // O que ele isola, desde que as matrizes passaram a ser sorteadas por
    // período: **sem retorno** o vão em conclusões é o mesmo nos dois presets
    // (−18% aqui, −17% no Computação), mas **com retorno** o leilão empata com
    // o CR no Computação (+1%) e continua 9% atrás aqui. Ou seja, o retorno
    // recupera conclusões justamente onde há dispersão de preferência para ele
    // explorar — e quase nada onde não há.
    build: (): SimulateRequest => ({
      ...commonScenario(),
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
