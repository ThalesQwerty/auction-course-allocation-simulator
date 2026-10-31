import type { DisciplineInput, Scenario } from "./types";

/** Um cenário pronto. */
export interface Preset {
  id: string;
  name: string;
  hint: string;
  build: () => Scenario;
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
 * preset: o aluno em dia cursa as seis do seu período e nada mais. As optativas
 * não entram nessa conta — não são de entrada, então a eq. (4) da matrícula
 * garantida só olha as seis. */
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

/** As **optativas**: sem pré-requisito, não destravam nada, e ficam de fora da
 * matrícula garantida. Concluir exige somar `ELECTIVE_HOURS` entre as que o
 * aluno aprovar — ele escolhe *quais*, e é essa substituibilidade que a
 * ordenação por CR não consegue expressar e o lance consegue.
 *
 * O catálogo é deliberadamente maior que a exigência: 1 560 h ofertadas contra
 * 480 h cobradas, o que deixa centenas de formas de cumprir o requisito e
 * mantém o conjunto elegível apertando a carga horária até o fim do curso.
 *
 * Três cargas em vez de duas. As de **30 h** não são variedade: com W_a = 450
 * divisível por 30, sobras de carga passam a ser preenchíveis exatamente, e a
 * mochila 0-1 da linha de base — que hoje quase nunca tem o que decidir —
 * ganha trabalho. Por isso mesmo elas serão procuradas por *caber*, e não por
 * serem desejadas: vão todas com 120 vagas, senão viram a coisa mais disputada
 * do cenário por um motivo que nada tem a ver com preferência. */
const OPTATIVAS: Entry[] = [
  // 12 x 60 h — o corpo do catálogo, vagas em 40/80/120
  ["Interação Humano-Computador", 60, 40, []],
  ["Desenvolvimento Web", 60, 80, []],
  ["Desenvolvimento Mobile", 60, 120, []],
  ["Programação Competitiva", 60, 40, []],
  ["Jogos Digitais", 60, 80, []],
  ["Robótica", 60, 120, []],
  ["Sistemas Embarcados", 60, 40, []],
  ["Bioinformática", 60, 80, []],
  ["Computação Quântica", 60, 120, []],
  ["Ética e Computação", 60, 40, []],
  ["Empreendedorismo em TI", 60, 80, []],
  ["Computação Musical", 60, 120, []],
  // 8 x 90 h — as caras, que ocupam um quinto da carga de um período
  ["Visão Computacional", 90, 40, []],
  ["Mineração de Dados", 90, 80, []],
  ["Computação Paralela", 90, 120, []],
  ["Otimização Combinatória", 90, 40, []],
  ["Teoria dos Jogos", 90, 80, []],
  ["Lógica para Computação", 90, 120, []],
  ["Linguagens Formais", 90, 40, []],
  ["Processamento de Imagens", 90, 80, []],
  // 4 x 30 h — as de encaixe, todas abundantes de propósito
  ["Seminários de Pesquisa", 30, 120, []],
  ["Oficina de Escrita Técnica", 30, 120, []],
  ["Tópicos em Software Livre", 30, 120, []],
  ["Introdução à Extensão", 30, 120, []],
];

/** X — carga horária optativa exigida para concluir. Com 2 700 h de
 * obrigatórias, o piso de períodos vai de ceil(2700/450) = 6 para
 * ceil(3180/450) = **8**: como W_a é exatamente um período da grade, cada hora
 * de optativa desloca uma hora de obrigatória. É por isso que |T| sobe junto. */
const ELECTIVE_HOURS = 480;


/** Carga horária máxima por período (W_a), igual para todos. É exatamente a
 * soma de um período da grade. */
/** Carga horária máxima por período (W_a). É a soma de um período da grade de
 * cada preset: quem está em dia cursa as seis disciplinas do seu período e
 * nada mais. */

const MAX_HOURS = HOURS.reduce((sum, h) => sum + h * SEATS.length, 0); // 450

/** Alunos que ingressam por período. O gargalo que dimensiona o cenário são
 * as disciplinas de 40 vagas: acima disso a fila nelas cresce sem drenar e
 * ninguém chega ao fim da grade; bem abaixo, nada aperta. */
const STUDENTS_PER_PERIOD = 60;

/** A população. **Não há perfis**: toda ela sai destas distribuições, e o que
 * distingue um aluno do outro é só o que a seed sorteou. */
const POPULATION = {
  // Nota média 6,5 com concentração 10 é a Beta(6,5, 3,5): desvio 0,14 e 84%
  // de aprovação numa disciplina de dificuldade 1.
  aptitude_mean: 0.65,
  aptitude_concentration: 10,
  // σ no pé da faixa: o aluno é quase indiferente entre as disciplinas de uma
  // mesma altura, e quem ordena a linha dele é sobretudo a invariante.
  utility_sigma: 0.25,
  max_hours: MAX_HOURS,
};

/** A dificuldade por patamar de oferta. Correlacionar as duas é escolha de
 * desenho, e é o que dá conteúdo à dificuldade: sozinha ela se cancela na
 * comparação, porque os dois mecanismos alocam a mesma mistura de disciplinas.
 * O canal dela é a **triagem** — a matrícula por CR dá a vaga disputada a quem
 * tem histórico alto, que é quem tem aptidão alta, e difícil + escassa é onde
 * isso rende. Vale incluir justamente por ser o melhor argumento do lado que a
 * hipótese do trabalho contesta.
 *
 * Lê-se em tentativas: 1,2 quer dizer que a disciplina custa uma tentativa e
 * um quinto para render o que uma de dificuldade 1 rende de primeira.
 *
 * **O tamanho do gradiente é calibragem, e custa caro.** As 40 vagas são
 * justamente a cadeia de pré-requisitos, de modo que a penalidade se compõe
 * ao longo dos seis níveis e atrasa todo mundo — não só quem a cursa. Medido
 * em seis braços, trocar {1, 1, 1} por {1,5, 1, 0,75} derruba os formados do
 * CR guloso de 158 para 107 e o psi de 0,095 para 0,083; {1,2, 1, 0,9} fica em
 * 140 e 0,091. Ficamos no gradiente médio: ele instala o canal da triagem sem
 * que o cenário inteiro vire um gargalo, e o vão entre os mecanismos quase não
 * muda com a escolha. É uma linha para mexer. */
const DIFFICULTY_BY_SEATS: Record<number, number> = { 40: 1.2, 80: 1, 120: 0.9 };

const toDisciplines = (groups: Entry[][]): DisciplineInput[] => {
  const flat = groups.flat();
  const unlocks = new Map<string, string[]>(flat.map(([name]) => [name, []]));
  for (const [name, , , dependsOn] of flat) {
    for (const predecessor of dependsOn) {
      unlocks.get(predecessor)?.push(name);
    }
  }
  const entry = new Set(P1.map(([name]) => name));
  return flat.map(([name, hours, seats]) => ({
    name,
    hours,
    seats,
    difficulty: DIFFICULTY_BY_SEATS[seats] ?? 1,
    unlocks: unlocks.get(name) ?? [],
    entry: entry.has(name),
  }));
};

const toElectives = (entries: Entry[]): DisciplineInput[] =>
  entries.map(([name, hours, seats]) => ({
    name,
    hours,
    seats,
    // Optativa fica em dificuldade 1: ela é o encaixe de carga, e dar-lhe
    // gradação misturaria dois efeitos no mesmo lugar.
    difficulty: 1,
    unlocks: [],
    entry: false,
    elective: true,
  }));

/** O que não varia entre execuções.
 *
 * O horizonte **não entra aqui**: |T| deixou de ser escolha e passou a sair do
 * ciclo de vida da população (`horizonFor`), que é o par ingresso × residência.
 * O que cada preset declara é quantos períodos recebem geração nova e quantos
 * o aluno tem para concluir antes de ser jubilado. */
const commonScenario = (
  disciplines: DisciplineInput[],
  studentsPerPeriod: number,
  electiveHours: number,
  entryPeriods: number,
  maxResidence: number,
): Omit<
  Scenario,
  | "aptitude_mean"
  | "aptitude_concentration"
  | "utility_sigma"
  | "max_hours"
  | "base_credits"
> => ({
  disciplines,
  elective_hours: electiveHours,
  // Depois do último ingresso vem a drenagem: ninguém mais entra e a população
  // só diminui. Sem ela as últimas gerações eram cortadas pelo horizonte antes
  // de poderem se formar — a última vivia um período só —, e a série por
  // geração media quanto tempo de simulação sobrou, não o mecanismo. Agora a
  // drenagem é consequência aritmética: o horizonte é ingresso + residência − 1,
  // então ela dura exatamente o que a última geração precisa para terminar.
  entry_periods: entryPeriods,
  max_residence: maxResidence,
  students_per_period: studentsPerPeriod,
  rounds: 2,
  min_grade: 5,
  // Padrões dos dois eixos novos: PLI global (o leilão do anteprojeto) e
  // orçamento que carrega entre períodos (eq. 36). A comparação os varia.
  resolver: "ilp",
  credit_memory: "carry",
  utility_gain: 0,
  // Metade do gosto persiste, metade recomeça a cada período. Em 0 — o que o
  // modelo fazia antes de a estabilidade existir — a preferência que não
  // persiste desfaz a fila sozinha, e é o valor que mais protege o lado fraco
  // da tese, então ele continua sendo o contraste a rodar. É a hipótese mais
  // exposta que resta: qualquer resultado em conclusões deve vir com este
  // valor declarado.
  utility_stability: 0.5,
  retake_gain: 1,
  credit_return: "none",
  seed: 42,
});


// ---------------------------------------------------------------------------
// O preset Fatorial — a grade como instrumento, não como retrato
// ---------------------------------------------------------------------------
//
// O Computação acima imita um currículo real. Este não imita nada: é um
// delineamento experimental. Três eixos binários cruzados, **todas as oito
// combinações presentes em todo período da grade**, de modo que carga,
// dificuldade e atratividade ficam balanceadas dentro de cada período e,
// portanto, ortogonais tanto ao período quanto às vagas. Uma diferença entre
// grupos é da grandeza em tela, nunca de composição.
//
// O preço desse desenho é que **vagas sai do fatorial no obrigatório**: elas
// variam por período (o funil), então ali não dá para separar "tem poucas
// vagas" de "é avançada". Quem recupera o eixo são as optativas, que não têm
// período: os três patamares de oferta cruzam o mesmo 2³. O obrigatório mede
// três eixos limpos, o optativo mede os quatro.

interface Cell {
  hours: number;
  difficulty: number;
  attractiveness: number;
}

/** As oito células do 2³, em ordem fixa. A ordem é o que faz a rotação por
 * período funcionar, então mexer nela muda o cenário. */
const CELLS: Cell[] = [
  { hours: 2, difficulty: 1, attractiveness: 1 },
  { hours: 2, difficulty: 1, attractiveness: 2 },
  { hours: 2, difficulty: 2, attractiveness: 1 },
  { hours: 2, difficulty: 2, attractiveness: 2 },
  { hours: 3, difficulty: 1, attractiveness: 1 },
  { hours: 3, difficulty: 1, attractiveness: 2 },
  { hours: 3, difficulty: 2, attractiveness: 1 },
  { hours: 3, difficulty: 2, attractiveness: 2 },
];

const CLASS_SIZE = 20;
const FACTORIAL_PERIODS = 6;

/** O **funil**: turmas por período, da entrada larga à ponta estreita. A
 * demanda por disciplina é constante ao longo da grade — todo aluno passa em
 * cada uma exatamente uma vez —, enquanto a oferta cai, de modo que a ocupação
 * sobe monotonicamente e a escassez fica concentrada no fim do curso.
 *
 * A ponta estreita é o que dimensiona o cenário: ela precisa entregar, por
 * período, tantas aprovações quantos alunos ingressam. Daí o teto de ingresso
 * ser `menor oferta × taxa de aprovação` — 80 × ~0,6 ≈ 48, e por isso
 * `FACTORIAL_STUDENTS` fica em 40, com folga. Acima disso a fila nos últimos
 * períodos cresce sem drenar e ninguém conclui. */
const CLASSES_BY_PERIOD = [9, 8, 7, 6, 5, 4];

/** **O sufixo é a célula.** `Obrigatória k.5` tem os mesmos três atributos em
 * qualquer período k, e a `Optativa g.5` também. Sufixo igual, atributos
 * iguais — em 72 disciplinas, é o que permite ler a grade sem consultar cada
 * cartão, e é o que torna o período a única coisa que varia ao longo de uma
 * linha da tela.
 *
 * Sobre esses rótulos corre a cadeia **triangular**: `k.j` destrava a
 * equivalente e a seguinte, `(k+1).j` e `(k+1).(j+1)`, com o sufixo 8 voltando
 * para o 1. Invertendo as arestas, **`(k+1).j` exige `k.j` e `k.(j−1)`** — e
 * pré-requisito aqui é conjuntivo (`eligible_set` pede `all(...)`), então são
 * as duas, não uma delas.
 *
 * O que isso custa, medido contra a diagonal simples no mesmo cenário: o
 * conjunto elegível cai de ~24,6 para ~17,5 disciplinas (−29%), o uso de W_a
 * de 88% para 82%, e o tempo de formatura sobe de 12,8 para ~13,5 períodos.
 * É o preço de uma grade que de fato se emaranha, em vez de oito cadeias que
 * nunca se encontram.
 *
 * O que **não** muda: todo nó de um período continua tendo seus sucessores no
 * período seguinte, então a altura segue uniforme dentro de cada período e a
 * invariante da eq. (41) continua fora do fatorial — os três eixos operam numa
 * única camada, que é onde sigma e a atratividade agem. Era essa a condição a
 * preservar, e a triangular a preserva. */
const nextSuffix = (suffix: number) => (suffix % CELLS.length) + 1;

const requiredName = (period: number, suffix: number) =>
  `Obrigatória ${period}.${suffix}`;

const FACTORIAL_REQUIRED: DisciplineInput[] = Array.from(
  { length: FACTORIAL_PERIODS * CELLS.length },
  (_, index) => {
    const period = Math.floor(index / CELLS.length) + 1;
    const suffix = (index % CELLS.length) + 1;
    const cell = CELLS[suffix - 1];
    return {
      name: requiredName(period, suffix),
      hours: cell.hours,
      seats: CLASSES_BY_PERIOD[period - 1] * CLASS_SIZE,
      difficulty: cell.difficulty,
      attractiveness: cell.attractiveness,
      unlocks:
        period < FACTORIAL_PERIODS
          ? [
              requiredName(period + 1, suffix),
              requiredName(period + 1, nextSuffix(suffix)),
            ]
          : [],
      // As oito do 1º período entram por matrícula garantida. Elas somam
      // 20 h, e é essa soma que fixa o piso de W_a: a eq. (4) exige que o
      // pacote inteiro caiba de uma vez, já que o ingressante o recebe sem
      // disputar e sem poder recusar.
      entry: period === 1,
    };
  },
);

/** As 24 optativas: três grupos de oito, cada grupo o 2³ completo num patamar
 * de oferta. Como optativa não tem período, aqui os **quatro** eixos ficam
 * cruzados — é o único lugar do cenário em que vagas é eixo medível.
 *
 * O grupo de 1 turma vai ser violentamente disputado: toda a população é
 * elegível a ele o tempo todo, porque optativa não tem pré-requisito. É o
 * ponto mais apertado do cenário, e é de propósito. */
const ELECTIVE_CLASSES = [3, 2, 1];

const FACTORIAL_ELECTIVES: DisciplineInput[] = ELECTIVE_CLASSES.flatMap(
  (classes, group) =>
    CELLS.map((cell, index) => ({
      name: `Optativa ${group + 1}.${index + 1}`,
      hours: cell.hours,
      seats: classes * CLASS_SIZE,
      difficulty: cell.difficulty,
      attractiveness: cell.attractiveness,
      unlocks: [] as string[],
      entry: false,
      elective: true,
    })),
);

/** W_a = 20 h, que é exatamente o que o 1º período oferece (4×2 + 4×3) — e o
 * piso imposto pela matrícula garantida, que entrega as oito de uma vez.
 *
 * Isso significa que o aluno **em dia** cursa o período inteiro e não escolhe
 * nada no lado obrigatório. Mas em dia quase ninguém está: metade do fatorial
 * é dificuldade 2, que exige aptidão ≥ 0,707 e só passa ~35% de primeira,
 * então o normal é carregar pendência — e aí o conjunto elegível passa de
 * W_a e a mochila volta a ter o que decidir. A escolha existe, só não é do
 * aluno exemplar: é de quem ficou para trás, que é quase todo mundo. */
const FACTORIAL_MAX_HOURS = 20;

/** X — exigência optativa, contra 60 h ofertadas no catálogo. A folga é o que
 * dá o que escolher; o teto é de capacidade, não de catálogo: as 24 optativas
 * entregam ~2 400 vaga-hora por período, e a `elective_hours × ingresso`
 * precisa caber nisso com folga. 30 h deixa ~40%. */
const FACTORIAL_ELECTIVE_HOURS = 30;

/** Ingresso por período: 2 turmas. O teto é a ponta do funil — ver
 * `CLASSES_BY_PERIOD`. */
const FACTORIAL_STUDENTS = 40;

export const PRESETS: Preset[] = [
  {
    id: "fatorial",
    name: "Fatorial",
    hint: "48 obrigatórias (6 × 8, as oito combinações de carga × dificuldade × atratividade em todo período) e 24 optativas, com cadeia triangular. Oferta em funil, 320 alunos em 8 gerações, 27 períodos.",
    build: (): Scenario => ({
      ...commonScenario(
        [...FACTORIAL_REQUIRED, ...FACTORIAL_ELECTIVES],
        FACTORIAL_STUDENTS,
        FACTORIAL_ELECTIVE_HOURS,
        // 8 gerações, e 20 períodos de residência em vez dos 12 do formulário
        // em branco: medido
        // em três seeds, o tempo de formatura fica em 13,7 períodos na média,
        // com cauda até 19. São 150 h a aprovar (120 de obrigatória + 30 de
        // optativa) e ~1,5 tentativa por disciplina na média do fatorial —
        // metade dele é dificuldade 2, que exige aptidão >= 0,707 e só passa
        // ~35% de primeira —, mais a espera pelo **par** de pré-requisitos que
        // a cadeia triangular impõe.
        //
        // O jubilamento **não morde** aqui: 100% concluem, 0% jubilam. É de
        // propósito. Jubilamento que morde censura o tempo de formatura, e aí
        // ele volta a medir quem sobreviveu em vez de quem foi rápido — o viés
        // de sobrevivência que o |T| = 14 do preset Computação escondia. Em 19
        // ele também não morde, mas sem folga nenhuma (a cauda bate exatamente
        // em 19); o período a mais é seguro e sai de graça, porque a simulação
        // para assim que a população esvazia. Quem quiser o jubilamento como
        // tratamento encurta a residência e lê o tempo com essa ressalva.
        // |T| = 8 + 20 - 1 = 27.
        8,
        20,
      ),
      ...POPULATION,
      max_hours: FACTORIAL_MAX_HOURS,
      // Γ_min alto porque o conjunto elegível é grande: ~8 obrigatórias do
      // período mais as 24 optativas, que não têm pré-requisito e estão sempre
      // abertas. Com poucos créditos o lance quantiza — o aluno não consegue
      // sequer diferenciar o que quer — e a mensagem vira um conjunto, que é
      // justamente o que a linha de base por CR já envia.
      base_credits: 60,
    }),
  },
  {
    id: "computacao",
    name: "Computação",
    hint: "Grade de 6 períodos × 6 disciplinas encadeadas, mais 24 optativas. 360 alunos em 6 gerações, 22 períodos.",
    build: (): Scenario => ({
      ...commonScenario(
        [...toDisciplines(GRADE), ...toElectives(OPTATIVAS)],
        STUDENTS_PER_PERIOD,
        ELECTIVE_HOURS,
        // 6 gerações — o piso teórico da grade, que tem seis elos de cadeia.
        //
        // Residência de 17, e não os 9 que reproduziriam o |T| = 14 histórico deste
        // preset. Com 9 o jubilamento morderia quase todo mundo: o piso para
        // concluir já é 8 períodos com as optativas, e na prática sai acima
        // disso. Pior, |T| = 14 era justamente o horizonte que **truncava** —
        // medido a 22 períodos, os três braços formam 360/360, e o vão em
        // diplomas que aparecia em 14 era a cauda direita da distribuição, não
        // lentidão. Dezessete dá à geração mais tardia os mesmos períodos que
        // ela tinha ali (22 − 6 + 1), de modo que o jubilamento não morde e o
        // tempo de formatura sai sem viés de sobrevivência. |T| = 22.
        6,
        17,
      ),
      ...POPULATION,
      // Γ_min = 40. Com ~12 elegíveis na fase em que a exigência optativa
      // ainda está pendente, 10 créditos truncavam o lance em 65% das linhas
      // por falta de crédito, e não por escolha: o aluno não conseguia nem pôr
      // 1 crédito em cada. Em 40 a truncagem cai para ~41% e volta a ser
      // decisão dele.
      base_credits: 40,
    }),
  },
];


export const defaultPreset = PRESETS[0];

/** Estado da escolha de cenário na tela de configuração. `presetId` null
 * significa "Personalizado"; `custom` guarda o cenário montado à mão para que
 * experimentar um preset não o perca. */
export interface PresetChoice {
  config: Scenario;
  presetId: string | null;
  custom: Scenario | null;
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
export function editConfig(_choice: PresetChoice, config: Scenario): PresetChoice {
  return { config, presetId: null, custom: config };
}
