import type {
  AffinityProfileInput,
  AptitudeProfileInput,
  DisciplineInput,
  SimulateRequest,
} from "./types";

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
 * Cada período soma 450 h, que é a carga horária máxima dos dois perfis de
 * afinidade (W_a): o aluno em dia cursa as seis disciplinas do seu período e
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

/** Carga horária máxima por período, igual nos dois perfis de afinidade. É
 * exatamente a soma de um período da grade. */
const MAX_HOURS = HOURS.reduce((sum, h) => sum + h * SEATS.length, 0); // 450

/** Alunos que ingressam por período. O teto formal é a menor oferta de 1º
 * período (120), mas quem dimensiona o cenário é o gargalo seguinte: as
 * disciplinas de 40 vagas, que a partir do 2º período servem toda a população
 * em dia. Acima disso a fila nelas cresce sem nunca drenar e ninguém chega ao
 * fim da grade; bem abaixo, nada aperta e não há escassez a alocar.
 *
 * Calibrado rodando o cenário. Com 60, ψ̄ anda entre 0,82 e 1,00 ao longo dos
 * períodos e ~28% concluem em 12, com a conclusão mais rápida em 6 — o piso da
 * cadeia. O recorte por vagas fica legível: as de 40 chegam a 1,3 candidato por
 * vaga e preço 2,5, enquanto as de 120 ficam em 0,4 e no piso de 1 crédito. Com
 * 30 a universidade inteira fica frouxa (ψ̄ = 1,00, preço sempre 1); com 70 a
 * fila nas de 40 vagas passa de 1,7 e a conclusão cai para 22%. */
const STUDENTS_PER_PERIOD = 60;

/** Perfis de aptidão do cenário Computação: a normal das notas de primeira
 * tentativa. As médias e os desvios separam três populações de desempenho bem
 * distintas — o Exemplar quase nunca reprova, o Instável reprova com frequência
 * e varia muito de uma disciplina para outra. As fatias são escolha de
 * calibragem (o enunciado fixa os parâmetros, não a proporção): metade da
 * população no perfil do meio e um quarto em cada extremo, que é a forma usual
 * de uma turma.
 *
 * O incremento por recursada é igual nos três, para que a diferença entre eles
 * seja só a distribuição das notas — é o eixo que o cenário quer isolar. */
const APTITUDE: AptitudeProfileInput[] = [
  { name: "Exemplar", mean: 8, stddev: 1, learning_gain: 2.5, share: 25 },
  { name: "Regular", mean: 6.5, stddev: 1.5, learning_gain: 2.5, share: 50 },
  { name: "Instável", mean: 5, stddev: 2, learning_gain: 2.5, share: 25 },
];

/** Perfis de afinidade: o quanto o aluno concentra a preferência. Metade a
 * metade, porque é a comparação que interessa — o leilão deveria servir melhor
 * quem concentra, já que é exatamente essa informação que a ordenação por CR
 * não capta, e com fatias iguais a diferença entre os dois é lida direto.
 *
 * A carga horária máxima é igual nos dois, pelo mesmo motivo do incremento:
 * isolar o eixo. Variá-la é o jeito de perguntar o que acontece quando quem
 * concentra também carrega menos por período. */
const AFFINITY: AffinityProfileInput[] = [
  { name: "Focados", kind: "concentrated", intensity: 2, max_hours: MAX_HOURS, share: 50 },
  { name: "Dispersos", kind: "diluted", intensity: 2, max_hours: MAX_HOURS, share: 50 },
];

/** Perfil único de aptidão do cenário Homogêneo. Toda a população sorteia a
 * nota da mesma normal e aprende o mesmo a cada recursada; os alunos continuam
 * diferindo entre si, porque a nota é sorteada aluno a aluno, mas não há mais
 * diferença **sistemática** entre grupos. */
const FLAT_APTITUDE: AptitudeProfileInput[] = [
  { name: "Único", mean: 6, stddev: 1, learning_gain: 2, share: 100 },
];

/** Perfil único de afinidade, e **neutro**: intensidade 1 dá expoente 1 nos
 * dois sentidos, então a utilidade sorteada vale como saiu, sem concentrar nem
 * diluir. Por isso o `kind` aqui não decide nada — fica `concentrated` só por
 * ser o primeiro do formulário. */
const FLAT_AFFINITY: AffinityProfileInput[] = [
  { name: "Único", kind: "concentrated", intensity: 1, max_hours: MAX_HOURS, share: 100 },
];

const toDisciplines = (groups: Entry[][]): DisciplineInput[] =>
  groups.flat().map(([name, hours, seats, prerequisites]) => ({
    name,
    hours,
    seats,
    prerequisites,
  }));

/** O que os dois presets têm em comum: a mesma universidade, a mesma população
 * e a mesma calibragem. Eles diferem só nos perfis e em Γ_min, que é
 * justamente o que faz um servir de controle do outro — qualquer diferença
 * entre eles vem do que foi declarado na chamada, não da oferta. */
const commonScenario = (): Omit<
  SimulateRequest,
  "aptitude_profiles" | "affinity_profiles" | "base_credits"
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
      aptitude_profiles: APTITUDE,
      affinity_profiles: AFFINITY,
      base_credits: 10,
    }),
  },
  {
    id: "homogeneo",
    name: "Homogêneo",
    hint: "A mesma universidade do Computação, com um único perfil de aptidão (6 ± 1, ganho 2) e um único de afinidade (neutro, intensidade 1), e Γ_min = 12. Serve de controle: sem diferença sistemática entre alunos, o que a comparação mostrar é do mecanismo.",
    // Existe para a comparação entre mecanismos. No Computação, parte do vão
    // entre CR e créditos pode vir de como cada um trata uma população
    // desigual: a ordenação por CR premia o Exemplar por construção, e o leilão
    // rende mais a quem concentra a preferência. Aqui não há a quem premiar —
    // um só perfil em cada eixo, e o de afinidade sem distorção alguma —, então
    // o que restar de diferença é da regra de alocação, não da composição da
    // população.
    //
    // Rodado (N = 10) antes de entrar na lista, e o cenário não sai degenerado:
    // ψ̄ 0,795 no CR contra 0,890 nos dois braços de crédito, φ 0,865 contra
    // 0,969, λ 0,553 contra ~0,05. A mesma forma do Computação, com uma
    // diferença que vale olhar: aqui o leilão **não forma menos gente** — 116
    // sem retorno e 120 com, contra 112 do CR, onde no Computação eram 102 e
    // 111 contra 139. Isto é, o contra-argumento mais forte contra o leilão
    // anda junto da heterogeneidade dos perfis, não do mecanismo.
    build: (): SimulateRequest => ({
      ...commonScenario(),
      aptitude_profiles: FLAT_APTITUDE,
      affinity_profiles: FLAT_AFFINITY,
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
