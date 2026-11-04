import type { SavedPreset } from "./savedPresets";
import type { DisciplineInput, Scenario } from "./types";

/** A população: os dois eixos de perfil mais o sigma do interesse.
 *
 * A repartição entre as combinações é **igualitária** — com 3 perfis em cada
 * eixo são 9 pares e ~11% da coorte em cada um —, de modo que o que o cenário
 * escolhe é quantos grupos existem, não que fatia cada um leva.
 *
 * `max_hours` não está aqui: é do cenário, porque é a soma de um período da
 * grade. */
const POPULATION = {
  // A nota mais provável é o pico da curva numa disciplina de dificuldade
  // padrão, de primeira. A **média** sai 1 a 2 pontos abaixo dela, porque a
  // cauda esquerda é longa, e é por ela que o "baixo" está calibrado: moda 6,5
  // dá média 4,96, que encosta em n_min = 5 — aquele grupo reprova em torno de
  // metade das vezes. Sem dispersão de desempenho ninguém reprova, a recursada
  // some do cenário e o CR vira ruído.
  //
  // As duas chances de ponta separam os grupos onde a moda sozinha não separa,
  // e são o que torna 0 e 10 alcançáveis: o forte quase nunca zera e tira 10
  // em 3% das disciplinas; o fraco zera em 3% e quase nunca tira 10.
  performance_profiles: [
    { name: "Alto desempenho", mode_grade: 9, zero_rate: 0.0005, max_rate: 0.03 },
    { name: "Médio desempenho", mode_grade: 8, zero_rate: 0.005, max_rate: 0.008 },
    { name: "Baixo desempenho", mode_grade: 6.5, zero_rate: 0.03, max_rate: 0.0015 },
  ],
  // As horas que o aluno tem para o período, resorteadas a cada semestre. As
  // modas são W_a, dois terços e um terço — 28 h, 20 h e 10 h —, e o que de
  // fato separa os três é a **chance de encher a carga**: a alta não exclui
  // nada em metade dos semestres, a baixa quase nunca chega lá.
  //
  // A moda fica logo abaixo de W_a na alta, e não em cima: com o pico no teto
  // não existe log-normal que ainda o alcance com a frequência pedida.
  availability_profiles: [
    { name: "Alta disponibilidade", mode_hours: 28, full_load_rate: 0.5 },
    { name: "Média disponibilidade", mode_hours: 20, full_load_rate: 0.05 },
    { name: "Baixa disponibilidade", mode_hours: 10, full_load_rate: 0.001 },
  ],
  // μ = 1 põe a moda da fonte em e^{μ−σ²} = 1, e a prévia se lê; ele não mexe
  // em alocação, porque some na normalização. σ = 1 dá coeficiente de variação
  // ~1,3: o aluno distingue as disciplinas sem desprezar quase todas.
  interest_mean: 1,
  interest_sigma: 1,
};

// ---------------------------------------------------------------------------
// O fatorial — a grade como instrumento, não como retrato
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

/** Alunos por turma do cenário padrão.
 *
 * Não entra na grade: a grade declara **turmas**, e a lotação é do cenário,
 * editável no formulário. É o botão de estresse — a mesma oferta sob 20 ou
 * sob 40 é o mesmo currículo com o dobro de aperto. */
export const DEFAULT_CLASS_SIZE = 25;
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
      classes: CLASSES_BY_PERIOD[period - 1],
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
      classes,
      difficulty: cell.difficulty,
      attractiveness: cell.attractiveness,
      unlocks: [] as string[],
      entry: false,
      elective: true,
    })),
);

/** W_a = 30 h, contra as 20 que o 1º período oferece (4×2 + 4×3).
 *
 * O piso é 20: a matrícula garantida entrega as oito de uma vez, e a eq. (4)
 * exige que o pacote inteiro caiba. A **folga de 10 h sobre o piso é
 * deliberada** — com W_a colado no piso o ingressante não tem o que decidir, e
 * pedido especulativo nenhum chega a existir para ser observado. Com folga, a
 * exclusão passa a ser escolha visível desde o 1º período.
 *
 * Fora da entrada a mochila já tinha o que decidir de qualquer jeito: metade
 * do fatorial é dificuldade 2, que exige aptidão ≥ 0,707 e só passa ~35% de
 * primeira, então o normal é carregar pendência e o conjunto elegível passa
 * de W_a. */
const FACTORIAL_MAX_HOURS = 30;

/** X — exigência optativa, contra 60 h ofertadas no catálogo. A folga é o que
 * dá o que escolher; o teto é de capacidade, não de catálogo: as 24 optativas
 * entregam ~2 400 vaga-hora por período, e a `elective_hours × ingresso`
 * precisa caber nisso com folga. 30 h deixa ~40%. */
const FACTORIAL_ELECTIVE_HOURS = 30;

/** Ingresso por período: uma coorte inteira de genótipos.
 *
 * 180 é o tamanho da grade de genes — 5 β_u × 3 β_v × 3 β_n × 4 α_u —, de modo
 * que a geração 1 da evolutiva tem **um exemplar de cada combinação notável** e
 * nenhuma delas pesa o dobro da outra. O número vem do genoma, não da grade.
 *
 * **O funil foi dimensionado para 40.** Medido numa seed, com 20 por turma a
 * conclusão caía de 77% para 40% e o jubilamento subia de 23% para 60%;
 * multiplicando toda a oferta por 4,5 ela voltava a 76% com o mesmo tempo de
 * formatura — é escassez de vaga, não efeito do tamanho da coorte.
 *
 * `class_size` tira parte da pressão sem mexer na estrutura: a 25 por turma as
 * oito do 1º período vão a 225 vagas, e os 45 que sobram sobre os ingressantes
 * são o que a recursada disputa. A 20 a matrícula garantida consumia a oferta
 * inteira e ninguém recursava uma disciplina de entrada enquanto houvesse
 * ingresso. Se 25 basta, não foi medido. */
const FACTORIAL_STUDENTS = 180;

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

/** **Os valores padrão do formulário**: o cenário que a tela abre antes de
 * qualquer escolha. Não é um preset entre outros — é o ponto de partida, e o
 * que cria alternativa é salvar.
 *
 * O horizonte **não entra aqui**: |T| deixou de ser escolha e passou a sair do
 * ciclo de vida da população (`horizonFor`), que é o par ingresso × residência.
 * O que se declara é quantos períodos recebem coorte nova e quantos o aluno
 * tem para concluir antes de ser jubilado. */
export const defaultScenario = (): Scenario => ({
  disciplines: GRADE,
  class_size: DEFAULT_CLASS_SIZE,
  students_per_period: FACTORIAL_STUDENTS,
  elective_hours: FACTORIAL_ELECTIVE_HOURS,
  max_hours: FACTORIAL_MAX_HOURS,
  // Depois do último ingresso vem a drenagem: ninguém mais entra e a população
  // só diminui. Sem ela as últimas coortes eram cortadas pelo horizonte antes
  // de poderem se formar — a última vivia um período só —, e a série por coorte
  // media quanto tempo de simulação sobrou, não o mecanismo. Agora a drenagem é
  // consequência aritmética: o horizonte é ingresso + residência − 1, então ela
  // dura exatamente o que a última coorte precisa para terminar.
  entry_periods: 8,
  // Residência: 16 períodos. São 150 h a aprovar (120 de optativa) e ~1,5
  // tentativa por disciplina na média do fatorial — metade dele é dificuldade
  // 2, que exige aptidão >= 0,707 e só passa ~35% de primeira —, mais a espera
  // pelo **par** de pré-requisitos que a cadeia triangular impõe.
  //
  // Aqui o jubilamento **morde**, e isso muda a leitura do tempo de formatura:
  // ele passa a medir quem sobreviveu, não quem foi rápido. É o viés de
  // sobrevivência de sempre, agora assumido como tratamento em vez de evitado.
  // |T| = 8 + 16 − 1 = 23.
  max_residence: 16,
  rounds: 3,
  min_grade: 5,
  // Padrões dos dois eixos novos: PLI global (o leilão do anteprojeto) e
  // orçamento que carrega entre períodos (eq. 36). A comparação os varia.
  resolver: "ilp",
  credit_memory: "carry",
  // Metade do gosto persiste, metade recomeça a cada período. Em 0 — o que o
  // modelo fazia antes de a estabilidade existir — a preferência que não
  // persiste desfaz a fila sozinha, e é o valor que mais protege o lado fraco
  // da tese, então ele continua sendo o contraste a rodar. É a hipótese mais
  // exposta que resta: qualquer resultado em conclusões deve vir com este valor
  // declarado.
  interest_stability: 0.5,
  credit_return: "none",
  seed: 42,
  ...POPULATION,
  // Γ_min alto porque o conjunto elegível é grande: ~8 obrigatórias do período
  // mais as 24 optativas, que não têm pré-requisito e estão sempre abertas. Com
  // poucos créditos o lance quantiza — o aluno não consegue sequer diferenciar
  // o que quer — e a mensagem vira um conjunto, que é justamente o que a linha
  // de base por CR já envia.
  base_credits: 60,
});

/** Estado da escolha de cenário na tela de configuração. `presetId` null
 * significa "Personalizado" — o cenário montado à mão, ou os valores padrão
 * enquanto nada foi mexido. `custom` guarda o que estava no formulário para
 * que carregar um salvo não o perca. */
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

/** Clique na lista: carrega um cenário salvo, ou volta ao personalizado —
 * que é o que o usuário montou ou, enquanto não montou nada, o padrão. Clicar
 * no que já está carregado não faz nada. */
export function choosePreset(
  choice: PresetChoice,
  id: string | null,
  saved: SavedPreset[] = []
): PresetChoice {
  if (id === choice.presetId) return choice;
  if (id === null) {
    return { ...choice, config: choice.custom ?? defaultScenario(), presetId: null };
  }
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
