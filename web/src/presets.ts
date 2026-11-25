import type { SavedPreset } from "./savedPresets";
import type { DisciplineInput, Scenario } from "./types";

/** A população: os quatro eixos de perfil mais o sigma do interesse.
 *
 * Dois são **traço** — desempenho e disponibilidade governam
 * sorteios, e o aluno não os conhece. O outro é **estratégia**: a
 * seletividade entra na decisão dele, e é por isso que vale valor fixo em vez
 * de distribuição. Um perfil de estratégia é tratamento, não descrição.
 *
 * Cada eixo é **uma distribuição só** mais um nível basilar: a fração da
 * variância que é permanente do aluno. Os perfis declarados saíram em
 * 19/11/2026, e com eles a coorte derivada do produto das combinações.
 *
 * `max_hours` não está aqui: é do cenário, porque é a soma de um período da
 * grade. */
const POPULATION: Pick<
  Scenario,
  | "performance"
  | "performance_stability"
  | "availability"
  | "availability_stability"
  | "selectivity_median"
  | "selectivity_sigma"
  | "selectivity_stability"
  | "grade_cuts"
  | "reserve_cuts"
  | "credit_cuts"
  | "interest_mean"
  | "interest_sigma"
> = {
  // A nota mais provável é o pico da curva numa disciplina de dificuldade
  // padrão, de primeira. A **média** sai 1 a 2 pontos abaixo dela, porque a
  // cauda esquerda é longa: moda 8 dá média em torno de 6,4, bem acima de
  // n_min = 5, e quem reprova é a cauda.
  performance: { mode_grade: 8, zero_rate: 0.005, max_rate: 0.008 },
  // **Sem este número não há CR que ordene.** O quantil do aluno é sorteado
  // por matéria; se nada o amarrasse, a média dos quantis de quem cursou
  // muita disciplina convergiria para 0,5 e a dispersão do CR entre alunos
  // cairia como 1/√D, sem piso. Medido na grade de 36 obrigatórias: o desvio
  // padrão do CR cai de ~1,05 para ~0,37, e continua caindo.
  //
  // 0,6 deixa espaço para "bom em cálculo e ruim em escrita" sem que o CR
  // deixe de separar as pessoas.
  performance_stability: 0.6,
  // As horas que o aluno tem para o período. A moda fica logo abaixo de W_a,
  // e não em cima: com o pico no teto não existe log-normal que ainda o
  // alcance com a frequência pedida. O que governa a exclusão é a **chance de
  // encher a carga**, não a moda.
  availability: { mode_hours: 16, full_load_rate: 0.05 },
  // Quanto do tempo livre é circunstância e quanto é vida: em 0 ninguém é
  // sistematicamente mais ocupado que ninguém, e o recorte por quantil
  // fatiaria o sorteio do semestre.
  availability_stability: 0.5,
  // A opção externa, na **escala do interesse**: a reserva do aluno é
  // `S / (S + ΣI)` sobre o interesse das elegíveis. A referência para
  // calibrar é `1/(turmas da grade)` — 1/288 aqui —, que põe o limiar na
  // utilidade média de uma elegível; medido, este valor admite 29% delas.
  // Perto de 0 está o **especulador**, que pede tudo e gasta o orçamento
  // inteiro; acima da referência o aluno poupa, e o crédito não investido
  // fica para o período seguinte. É o eixo que torna observável se especular
  // compensa.
  selectivity_median: 0.0035,
  selectivity_sigma: 0.6,
  // Mais estável que os outros dois: exigência é feitio, não semestre.
  selectivity_stability: 0.7,
  // Três faixas em cada eixo — o semáforo, que é a escada que mais se lê de
  // relance. Os valores saem da distribuição medida no cenário calibrado: a
  // mediana do CR fica perto de 5,6, e a da reserva em 0,015 com p90 em 0,056,
  // daí os cortes dela caírem nos milésimos. Trocar de cenário pede recalibrar.
  grade_cuts: [5, 7],
  reserve_cuts: [0.01, 0.03],
  credit_cuts: [15, 20],
  // μ = 1 põe a moda da fonte em e^{μ−σ²} = 1, e a prévia se lê; ele não mexe
  // em alocação, porque some na normalização. σ = 1 dá coeficiente de variação
  // ~1,3: o aluno distingue as disciplinas sem desprezar quase todas.
  interest_mean: 1,
  interest_sigma: 1,
};

/** Os eixos da população que um cenário salvo antes deles pode não trazer. É
 * o que a API já assume quando o campo vem ausente, então preencher aqui não
 * muda o que aquele cenário rodava. */
export const strategyDefaults = () => ({ ...POPULATION });

// ---------------------------------------------------------------------------
// O fatorial — a grade como instrumento, não como retrato
// ---------------------------------------------------------------------------
//
// Não imita um currículo real: é um delineamento experimental. Carga e
// dificuldade cruzadas, **todas as seis combinações presentes em todo período
// da grade**, de modo que as duas ficam balanceadas dentro de cada período e,
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
  /** Em quantas tentativas a disciplina custa o que uma de dificuldade 1
   * rende de primeira. */
  difficulty: number;
}

/** **A dificuldade voltou para a disciplina.** Ela foi eixo da turma
 * enquanto existiu a escada de `class_difficulty_levels`; com a escada e a
 * atratividade fora, o que distingue as turmas de uma disciplina passou a ser
 * o **turno** — e o que distingue as disciplinas entre si voltou a ser carga
 * e dificuldade.
 *
 * O centro geométrico de (1 · 1,4 · 2) é 1,41, o **mesmo** da escada que
 * saiu: a calibragem da aprovação não muda, só muda de camada. */
const CELL_HOURS = [2, 3];
const CELL_DIFFICULTY = [1, 1.4, 2];

/** As seis células, em ordem fixa — 2 cargas × 3 dificuldades. A ordem é o
 * que faz a rotação por período funcionar, então mexer nela muda o cenário.
 *
 * Os dois eixos não estão na mesma unidade, e é preciso ter isso em conta ao
 * comparar a grandeza dos efeitos: carga é **múltiplo** (1,5× entre as
 * pontas), dificuldade é o expoente recíproco de `attempt_rates` (2× entre as
 * pontas). */
const CELLS: Cell[] = CELL_HOURS.flatMap((hours) =>
  CELL_DIFFICULTY.map((difficulty) => ({ hours, difficulty }))
);

/** Alunos por turma do cenário padrão.
 *
 * Não entra na grade: a grade declara **turmas**, e a lotação é do cenário,
 * editável no formulário. É o botão de estresse — a mesma oferta sob 20 ou
 * sob 40 é o mesmo currículo com o dobro de aperto. */
export const DEFAULT_CLASS_SIZE = 45;
const FACTORIAL_PERIODS = 6;

/** O **funil**: turmas por período, da entrada larga à ponta estreita. A
 * demanda por disciplina é constante ao longo da grade — todo aluno passa em
 * cada uma exatamente uma vez —, enquanto a oferta cai, de modo que a ocupação
 * sobe monotonicamente e a escassez fica concentrada no fim do curso.
 *
 * A ponta estreita é o que dimensiona o cenário: ela precisa entregar, por
 * período, tantas aprovações quantos alunos ingressam. O teto de ingresso é
 * `menor oferta × taxa de aprovação`, e a menor oferta são as 4 turmas de
 * `class_size` de cada disciplina do 6º período — contra a coorte inteira,
 * que precisa passar em cada uma delas. Acima desse teto a fila dos últimos
 * períodos cresce sem drenar, e quem fica nela é jubilado em vez de concluir. */
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
 * período seguinte, então a altura segue uniforme dentro de cada período —
 * os eixos operam numa única camada, que é onde sigma age. Era essa a
 * condição a preservar, e a triangular a preserva. */
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
      unlocks:
        period < FACTORIAL_PERIODS
          ? [
              requiredName(period + 1, shiftSuffix(suffix, 1)),
              requiredName(period + 1, shiftSuffix(suffix, 2)),
            ]
          : [],
      // As seis do 1º período entram por matrícula garantida. Elas somam
      // 15 h, e é essa soma que fixa o piso de W_a: a eq. (4) exige que o
      // pacote inteiro caiba de uma vez, já que o ingressante o recebe sem
      // disputar e sem poder recusar.
      entry: period === 1,
    };
  },
);

/** As 27 optativas: três grupos de nove, cada grupo o cruzamento completo num
 * patamar de oferta. Como optativa não tem período, ela pode levar **três**
 * cargas horárias em vez das duas do obrigatório — e é o único lugar do
 * cenário em que vagas é eixo medível.
 *
 * O grupo de 1 turma vai ser violentamente disputado: toda a população é
 * elegível a ele o tempo todo, porque optativa não tem pré-requisito. É o
 * ponto mais apertado do cenário, e é de propósito. */
const ELECTIVE_CLASSES = [3, 2, 1];
const ELECTIVE_HOURS = [1, 2, 3];

const ELECTIVE_CELLS: Cell[] = ELECTIVE_HOURS.flatMap((hours) =>
  CELL_DIFFICULTY.map((difficulty) => ({ hours, difficulty }))
);

const FACTORIAL_ELECTIVES: DisciplineInput[] = ELECTIVE_CLASSES.flatMap(
  (classes, group) =>
    ELECTIVE_CELLS.map((cell, index) => ({
      name: `Optativa ${group + 1}.${index + 1}`,
      hours: cell.hours,
      classes,
      difficulty: cell.difficulty,
      unlocks: [] as string[],
      entry: false,
      elective: true,
    })),
);

/** W_a = 24 h, contra as 15 que o 1º período oferece (3×2 + 3×3).
 *
 * O piso é 15: a matrícula garantida entrega as seis de uma vez, e a eq. (4)
 * exige que o pacote inteiro caiba. A **folga sobre o piso é deliberada** —
 * com W_a colado no piso o ingressante não tem o que decidir, e pedido
 * especulativo nenhum chega a existir para ser observado. Com folga, a
 * exclusão passa a ser escolha visível desde o 1º período.
 *
 * Caiu de 30 com o pacote de entrada, que foi de 20 h para 15 quando a
 * atratividade saiu das células e elas passaram de oito para seis. A razão
 * folga/piso é a mesma de antes: 1,6. */
const FACTORIAL_MAX_HOURS = 24;

/** X — exigência optativa, contra 54 h ofertadas no catálogo (três grupos de
 * 1+2+3 h em cada nível de dificuldade). A folga é o que dá o que escolher.
 *
 * O teto real é de **capacidade**, não de catálogo: o catálogo entrega
 * `Σ turmas × class_size × carga` vaga-hora por período, e em regime a coorte
 * inteira consome `X` horas optativas por período. Caiu de 30 na mesma
 * proporção do obrigatório, que foi de 48 h para 36. */
const FACTORIAL_ELECTIVE_HOURS = 24;

/** Ingressantes em cada turma de disciplina de entrada.
 *
 * A **coorte sai daqui**: 30 em cada uma das 9 turmas do 1º período dão 270
 * alunos por período. Contra a lotação de 45, sobram 15 vagas por turma de
 * entrada para quem recursa, e é essa folga que decide se o reprovado volta a
 * cursar a disciplina.
 *
 * Eram **exemplares por combinação de perfil** até 19/11/2026, com a coorte
 * saindo de 2 × 135 combinações. Os perfis saíram e o número ficou para trás:
 * o cenário padrão abriu com coorte de 2 até 24/11/2026. */
const FACTORIAL_ENTRANTS_PER_CLASS = 30;

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
 * janela estacionária (`horizonFor`), que é o par jubilamento × observação.
 * O que se declara é quantos períodos recebem coorte nova e quantos o aluno
 * tem para concluir antes de ser jubilado. */
export const defaultScenario = (): Scenario => ({
  disciplines: GRADE,
  class_size: DEFAULT_CLASS_SIZE,
  students_per_entry_class: FACTORIAL_ENTRANTS_PER_CLASS,
  elective_hours: FACTORIAL_ELECTIVE_HOURS,
  max_hours: FACTORIAL_MAX_HOURS,
  // Depois do último ingresso vem a drenagem: ninguém mais entra e a população
  // só diminui. Sem ela as últimas coortes eram cortadas pelo horizonte antes
  // de poderem se formar — a última vivia um período só —, e a série por coorte
  // media quanto tempo de simulação sobrou, não o mecanismo. Agora a drenagem é
  // consequência aritmética: o horizonte é ingresso + residência − 1, então ela
  // dura exatamente o que a última coorte precisa para terminar.
  observation_periods: 10,
  // Residência: 16 períodos. São 60 h a aprovar (24 de optativa) e ~1,5
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
  // Metade do gosto persiste, metade recomeça a cada período. Em 0 — o que o
  // modelo fazia antes de a estabilidade existir — a preferência que não
  // persiste desfaz a fila sozinha, e é o valor que mais protege o lado fraco
  // da tese, então ele continua sendo o contraste a rodar. É a hipótese mais
  // exposta que resta: qualquer resultado em conclusões deve vir com este valor
  // declarado.
  interest_stability: 0.5,
  // Quanto do interesse é comum às turmas da mesma disciplina. Em 0,7 o aluno
  // tem preferência de turma — sem ela, todas valem o mesmo e a escolha de
  // turma deixa de ser decisão —, mas a disciplina continua mandando: é dela
  // que vem a maior parte do valor.
  class_stability: 0.7,
  // Os horários. Cada um é um grupo de exclusão mútua, e as turmas da grade
  // caem neles em círculo. O piso é o maior número de turmas de uma
  // disciplina — 9 na grade padrão —, e reduzi-los é o botão para o conflito
  // pesar mais.
  slots: 12,
  seed: 42,
  ...POPULATION,
  // C_min e C_max são um par, e a escolha entre eles é um troco conhecido.
  // Sem teto, a eq. (36) acumulava até 900 créditos — quinze vezes o piso de
  // 60 — em quem é seletivo o bastante para não gastar, e poder de compra
  // vindo da abstenção é o contrário do que o retorno da eq. (34) premia.
  // Com teto, o piso pode cair, e cai: 12 de orçamento mínimo, 30 de máximo.
  //
  // O custo é a quantização do lance, e ele é real. O conjunto elegível é
  // grande — ~8 obrigatórias do período mais as 24 optativas, sempre abertas —,
  // e com 12 créditos o aluno não cobre o que quer sem empatar quase tudo em 1
  // (medido com o ganho base do anteprojeto: a fração de lances de 1 crédito
  // sobe de 53% com 60 para 68% com 20). A mensagem se aproxima de um
  // conjunto, que é o que a linha de base por CR já envia. É escolha
  // deliberada: o teto importa mais.
  min_credits: 12,
  max_credits: 30,
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
