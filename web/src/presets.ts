import type { SavedPreset } from "./savedPresets";
import type { DisciplineInput, Scenario } from "./types";

/** Um cenário pronto. */
export interface Preset {
  id: string;
  name: string;
  hint: string;
  build: () => Scenario;
}

/** A população: os dois eixos de perfil mais o sigma das utilidades.
 *
 * A repartição entre as combinações é **igualitária** — com 3 perfis em cada
 * eixo são 9 pares e ~11% da geração em cada um —, de modo que o que o cenário
 * escolhe é quantos grupos existem, não que fatia cada um leva.
 *
 * `max_hours` não está aqui: é do preset, porque é a soma de um período da
 * grade dele. */
const POPULATION = {
  // Com dificuldade 1 e sem ganhos a nota **é** a aptidão × 10, então a média
  // se lê direto como a nota típica do grupo — e n_min = 5 põe a fronteira da
  // reprovação em 0,5. Sem dispersão de desempenho ninguém reprova, a
  // recursada some do cenário e o CR vira ruído.
  performance_profiles: [
    { name: "Alto desempenho", mean: 0.8, concentration: 25 },
    { name: "Médio desempenho", mean: 0.65, concentration: 15 },
    { name: "Baixo desempenho", mean: 0.5, concentration: 10 },
  ],
  // A fração de W_a que o aluno de fato cursa, resorteada a cada período.
  // "integral" concentra junto do teto e quase nunca exclui; "reduzida" é
  // larga e raramente passa de 0,8.
  availability_profiles: [
    { name: "Alta disponibilidade", mean: 0.95, concentration: 50 },
    { name: "Média disponibilidade", mean: 0.85, concentration: 20 },
    { name: "Baixa disponibilidade", mean: 0.6, concentration: 10 },
  ],
  // σ no pé da faixa: o aluno é quase indiferente entre as disciplinas de uma
  // mesma altura, e quem ordena a linha dele é sobretudo a invariante.
  utility_sigma: 0.25,
};

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
  | "performance_profiles"
  | "availability_profiles"
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
// Não imita um currículo real: é um delineamento experimental. Três eixos binários cruzados, **todas as oito
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
  /** Deslocamento do expoente, não múltiplo: ver `CELLS`. */
  attractiveness: number;
}

/** As oito células do 2³, em ordem fixa. A ordem é o que faz a rotação por
 * período funcionar, então mexer nela muda o cenário.
 *
 * Os três eixos não estão na mesma unidade, e é preciso ter isso em conta ao
 * comparar a grandeza dos efeitos: carga e dificuldade são **múltiplos** (1,5×
 * e 2×), a atratividade é **deslocamento do expoente**, de modo que o par
 * (0, 1) vale e ≈ 2,72× entre os dois níveis. */
const CELLS: Cell[] = [
  { hours: 2, difficulty: 1, attractiveness: 0 },
  { hours: 2, difficulty: 1, attractiveness: 1 },
  { hours: 2, difficulty: 2, attractiveness: 0 },
  { hours: 2, difficulty: 2, attractiveness: 1 },
  { hours: 3, difficulty: 1, attractiveness: 0 },
  { hours: 3, difficulty: 1, attractiveness: 1 },
  { hours: 3, difficulty: 2, attractiveness: 0 },
  { hours: 3, difficulty: 2, attractiveness: 1 },
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
 * Sobre esses rótulos corre a cadeia **triangular**: `k.j` destrava as duas
 * células seguintes, `(k+1).(j+1)` e `(k+1).(j+2)`, com o sufixo dando a volta
 * no 8. Invertendo as arestas, **`(k+1).j` exige `k.(j−1)` e `k.(j−2)`** — e
 * pré-requisito aqui é conjuntivo (`eligible_set` pede `all(...)`), então são
 * as duas, não uma delas. O cone para a frente de `1.1` é a figura que batiza
 * a cadeia — uma frente que ganha uma disciplina por período:
 *
 *     1.1 → 2.2 2.3 → 3.3 3.4 3.5 → 4.4 4.5 4.6 4.7
 *         → 5.5 5.6 5.7 5.8 5.1 → 6.6 6.7 6.8 6.1 6.2 6.3
 *
 * O deslocamento é de **uma célula, não de zero**, e é aí que a cadeia paga
 * seu aluguel no fatorial: nenhuma aresta liga duas disciplinas de mesmo
 * sufixo, então a célula de uma disciplina é independente da célula dos seus
 * pré-requisitos. Fosse `(k+1).j ← k.j`, metade das arestas ligaria atributos
 * idênticos e "ser difícil" viria correlacionado com "ter pré-requisito
 * difícil" — um confundimento dentro do próprio desenho, justamente o que o
 * 2³ existe para evitar.
 *
 * O que o par de pré-requisitos custa, medido em três seeds contra a diagonal
 * simples — um sucessor só por disciplina, que são oito cadeias paralelas que
 * nunca se encontram: o conjunto elegível cai de ~25,2 para ~20,6 disciplinas
 * (−18%), o uso de W_a de 95% para 92%, e o tempo de formatura sobe de 12,8
 * para ~13,1 períodos. É o preço de uma grade que de fato se emaranha.
 *
 * O deslocamento de uma célula, por sua vez, **sai de graça e ainda devolve
 * troco**: contra o par (+0, +1) — o que fazia cada disciplina herdar a
 * própria célula —, a formatura cai de 13,6 para 13,1 períodos e a cauda de
 * ~19 para 17. É o que se espera: ali a dificuldade vinha correlacionada ao
 * longo da cadeia, então o atraso numa disciplina difícil recaía sobre outra
 * difícil, na mesma linhagem, e os atrasos se compunham.
 *
 * O que **não** muda: todo nó de um período continua tendo seus sucessores no
 * período seguinte, então a altura segue uniforme dentro de cada período e a
 * invariante da eq. (41) continua fora do fatorial — os três eixos operam numa
 * única camada, que é onde sigma e a atratividade agem. Era essa a condição a
 * preservar, e a triangular a preserva. */
const shiftSuffix = (suffix: number, by: number) =>
  ((suffix - 1 + by) % CELLS.length) + 1;

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
              requiredName(period + 1, shiftSuffix(suffix, 1)),
              requiredName(period + 1, shiftSuffix(suffix, 2)),
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

/** **A grade, única para todo o aplicativo.**
 *
 * A oferta não é parâmetro de cenário: o formulário não a edita, e quem a
 * mostra é a tela Grade. Guardar uma cópia dela em cada preset salvo seria
 * guardar algo que pode divergir da única que existe — então os salvos
 * carregam só os parâmetros, e a grade vem daqui ao carregar.
 *
 * Mudar esta lista muda todos os cenários de uma vez, que é exatamente o que
 * "a grade é a mesma para todos" quer dizer. */
export const GRADE: DisciplineInput[] = [...FACTORIAL_REQUIRED, ...FACTORIAL_ELECTIVES];

export const PRESETS: Preset[] = [
  {
    id: "fatorial",
    name: "Fatorial",
    hint: "48 obrigatórias (6 × 8, as oito combinações de carga × dificuldade × atratividade em todo período) e 24 optativas, com cadeia triangular. Oferta em funil, 320 alunos em 8 gerações, 27 períodos.",
    build: (): Scenario => ({
      ...commonScenario(
        GRADE,
        FACTORIAL_STUDENTS,
        FACTORIAL_ELECTIVE_HOURS,
        // 8 gerações, e 20 períodos de residência em vez dos 12 do formulário
        // em branco: medido em cinco seeds, o tempo de formatura fica em 13,1
        // períodos na média, com cauda em 17. São 150 h a aprovar (120 de
        // optativa) e ~1,5 tentativa por disciplina na média do fatorial —
        // metade dele é dificuldade 2, que exige aptidão >= 0,707 e só passa
        // ~35% de primeira —, mais a espera pelo **par** de pré-requisitos que
        // a cadeia triangular impõe.
        //
        // O jubilamento **não morde** aqui: 100% concluem, 0% jubilam. É de
        // propósito. Jubilamento que morde censura o tempo de formatura, e aí
        // ele volta a medir quem sobreviveu em vez de quem foi rápido — o viés
        // de sobrevivência que o |T| = 14 do preset Computação escondia. Com
        // 20 sobram três períodos sobre a cauda medida — folga que não custa
        // nada, porque a simulação para assim que a população esvazia e de
        // fato ela usa ~22 dos 27. Quem quiser o jubilamento como tratamento
        // encurta a residência e lê o tempo com essa ressalva.
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

/** Clique na lista: carrega o preset — pronto ou salvo pelo usuário — ou volta
 * ao cenário personalizado. Clicar no que já está carregado não faz nada,
 * inclusive não descarta o cenário personalizado guardado.
 *
 * Os dois tipos dividem o mesmo endereçamento: um id é um id, venha da lista
 * fixa ou do navegador. Os salvos levam prefixo próprio, então não colidem. */
export function choosePreset(
  choice: PresetChoice,
  id: string | null,
  saved: SavedPreset[] = []
): PresetChoice {
  if (id === choice.presetId) return choice;
  if (id === null) {
    return choice.custom ? { ...choice, config: choice.custom, presetId: null } : choice;
  }
  const preset = PRESETS.find((p) => p.id === id);
  if (preset) return { ...choice, config: preset.build(), presetId: id };
  // O salvo guarda só os parâmetros: a grade é a mesma para todos, e vem
  // daqui no momento de carregar.
  const stored = saved.find((p) => p.id === id);
  return stored
    ? { ...choice, config: { ...stored.config, disciplines: GRADE }, presetId: id }
    : choice;
}

/** Qualquer alteração no formulário passa a valer como cenário personalizado. */
export function editConfig(_choice: PresetChoice, config: Scenario): PresetChoice {
  return { config, presetId: null, custom: config };
}
