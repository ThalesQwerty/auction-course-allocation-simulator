// Espelha src/leilao/api/schemas.py

export interface DisciplineInput {
  name: string;
  /** Turmas ofertadas. As vagas são `classes × class_size`: a grade diz a
   * estrutura da oferta, o cenário diz a lotação. */
  classes: number;
  hours: number; // w_x — carga horária
  /** A dificuldade, em quantas tentativas a disciplina custa para render o
   * que uma de dificuldade 1 rende de primeira. Na fórmula da nota ela entra
   * dividida pela tentativa. Opcional: ausente é 1. */
  difficulty?: number;
  /** Sucessores: disciplinas que esta desbloqueia. Vazio = terminal, altura 0. */
  unlocks: string[];
  /** Matrícula garantida de quem ingressa. É **flag**, não dedução: não ter
   * pré-requisito não faz a disciplina ser de entrada — a optativa também não
   * tem e fica fora da garantia. */
  entry: boolean;
  /** A_x — atratividade: o **multiplicador** do interesse sorteado, comum a
   * toda a população. 1 é a disciplina média, 2 vale o dobro dela e 0,5 a
   * metade. É a parte do gosto comum a todos, enquanto `interest_sigma` é a
   * privada de cada aluno. Opcional: ausente é 1. */
  attractiveness?: number;
  /** Optativa: não desbloqueia nada, não é de entrada, e concluir não exige
   * aprovar em cada uma — exige somar `elective_hours` entre as aprovadas. É
   * isso que as torna substituíveis entre si. Ortogonal a `entry`. */
  elective?: boolean;
  /** Quanto do gosto por esta disciplina é permanente, de 0 a 1. Ausente cai
   * no valor do cenário. Declarar por disciplina sincroniza a persistência
   * entre concorrentes, e é essa sincronia que trava a fila. */
  stability?: number;
}

/** Política de retorno de créditos f_γ — eq. (34). Espelha
 * `leilao.config.CreditReturnPolicy`; o que cada uma faz está em
 * `CREDIT_RETURN_POLICIES`. */
export type CreditReturnPolicy = "none" | "unit" | "full" | "ratio";

/** As políticas na ordem em que aparecem no formulário, da mais restritiva à
 * mais generosa. Vive aqui, junto do tipo, para que acrescentar uma política
 * no motor quebre a compilação enquanto o rótulo não existir. */
export const CREDIT_RETURN_POLICIES: {
  value: CreditReturnPolicy;
  label: string;
  hint: string;
}[] = [
  { value: "none", label: "nenhum", hint: "o crédito gasto não volta — linha de base" },
  { value: "unit", label: "unitário", hint: "1 crédito por aprovação, qualquer que tenha sido o preço" },
  { value: "full", label: "integral", hint: "devolve o preço inteiro a quem aprova" },
  {
    value: "ratio",
    label: "proporcional",
    hint: "devolve a fatia do preço correspondente à nota, mesmo sem aprovação",
  },
];

export const creditReturnLabel = (policy: CreditReturnPolicy): string =>
  CREDIT_RETURN_POLICIES.find((option) => option.value === policy)?.label ?? policy;

/** Nome de uma coorte — o grupo que ingressou naquele período (coorte 3 =
 * quem entrou no período 3, esteja ele hoje em que semestre estiver). O aluno
 * nasce numa coorte e fica nela até o fim, que é o que mantém cada série
 * falando sempre do mesmo conjunto de alunos.
 *
 * Com os cursos fora do modelo, a coorte é o único recorte de aluno que
 * sobra — e é também o que mais separa as curvas, porque a posição na cadeia de
 * pré-requisitos é o que de fato distingue um aluno de outro aqui. */
export const cohortLabel = (entryPeriod: number): string => `Coorte ${entryPeriod}`;

/** Um grupo da população no eixo de **desempenho**.
 *
 * A nota sai de uma normal dividida censurada em [0, 10], descrita pelas três
 * grandezas que se leem: nota mais provável, chance de tirar 0 e chance de
 * tirar 10. A moda é a locação — o número digitado é o pico da curva —, a
 * chance de zero fixa a cauda esquerda e a de dez fixa a direita. A média sai
 * derivada, 1 a 2 pontos abaixo da moda.
 *
 * As três valem para a **disciplina de dificuldade 1 na primeira tentativa**.
 *
 * Espelha `api.schemas.PerformanceProfileIn`. */
export interface PerformanceProfile {
  /** Rótulo de relatório; precisa ser único dentro do seu eixo. */
  name: string;
  /** Cor do grupo nos gráficos. Ausente em cenário gravado antes dela: a tela
   * cai na paleta por posição (`profileColor`). */
  color?: string;
  mode_grade: number; // em (0, 10)
  zero_rate: number; // em (0, 1)
  max_rate: number; // em (0, 1)
}

/** Um grupo da população no eixo de **disponibilidade**.
 *
 * A disponibilidade é a carga que o aluno tem para o período, **em horas**, e
 * sai de uma log-normal — suporte (0, ∞), sem máximo artificial e nunca
 * negativa. O grupo a descreve pela **moda** (o pico da curva, em horas) e
 * pela **chance de alcançar a carga máxima**, que é a frequência com que ele
 * não precisa excluir nada.
 *
 * Passar de W_a é legítimo: o teto de carga é do sistema, não do aluno, e quem
 * o aplica é o alocador. A moda, essa sim, tem de ficar abaixo de W_a.
 *
 * Espelha `api.schemas.ProfileIn`. */
export interface Profile {
  /** Rótulo de relatório; precisa ser único dentro do seu eixo. */
  name: string;
  color?: string;
  mode_hours: number; // > 0, abaixo de W_a
  full_load_rate: number; // em (0, 1)
}

/** Um grupo da população no eixo de **seletividade** — o primeiro dos dois
 * eixos de *estratégia*, que o aluno conhece e usa, ao contrário dos dois de
 * traço (desempenho e disponibilidade), que governam sorteios por trás dele.
 *
 * O valor é um múltiplo do score médio das disciplinas elegíveis: abaixo de
 * `valor × média` o aluno não pede nem financia. Em 0 não há corte — é o
 * especulador, que pede tudo e gasta o orçamento inteiro. Acima de 1 ele
 * poupa: o crédito não investido fica para o período seguinte.
 *
 * Espelha `api.schemas.SelectivityProfileIn`. */
export interface SelectivityProfile {
  name: string;
  color?: string;
  value: number; // >= 0
}

/** Um grupo da população no eixo de **concentração**.
 *
 * O expoente do score sobre a utilidade: 1 é o lance sincero, abaixo achata,
 * acima concentra, e negativo inverte — aposta mais no que ele quer menos, que
 * é o controle do absurdo.
 *
 * Espelha `api.schemas.ConcentrationProfileIn`. */
export interface ConcentrationProfile {
  name: string;
  color?: string;
  value: number; // entre -3 e 5
}

export interface Scenario {
  disciplines: DisciplineInput[];
  /** Alunos por turma — `q_x = classes × este`. É o botão de estresse do
   * cenário: a mesma grade sob 20 ou 40 por turma é o mesmo currículo com o
   * dobro de aperto. */
  class_size: number;
  /** Perfis de **desempenho**: governam a normal dividida da nota, e por aí a
   * frequência com que o aluno reprova. O que o aluno carrega por disciplina é
   * o **quantil** dele naquela matéria, sorteado uma vez e persistente — traço,
   * não sorte. A dificuldade e a tentativa movem a distribuição sob esse
   * quantil, transformando as duas chances de ponta por expoentes recíprocos.
   *
   * O latente é ilimitado; o que limita é o instrumento. A nota é arredondada
   * em décimos e clipada em [0, 10], e é essa censura que torna o 0 e o 10
   * alcançáveis — com a frequência que o perfil declarou. */
  performance_profiles: PerformanceProfile[];
  /** Perfis de **disponibilidade**: governam a log-normal das horas que o
   * aluno tem para o período, sorteada **a cada período** — ao contrário do
   * quantil de desempenho, que é um só para o curso inteiro. O tempo disponível é
   * circunstância; o que é traço é a média de onde ela sai.
   *
   * Depois da última rodada o aluno descarta o que não couber nessa fração, e
   * o descartado vira solicitação **excluída**: não conta carga, não conta
   * tentativa, não mexe no CR, e no leilão devolve metade do preço pago. A
   * vaga não volta para a oferta. */
  availability_profiles: Profile[];
  /** Perfis de **seletividade** e de **concentração**: os dois eixos de
   * estratégia. Com os de traço eles dão as combinações de perfil, e a coorte
   * é `students_per_profile` vezes esse número. */
  selectivity_profiles: SelectivityProfile[];
  concentration_profiles: ConcentrationProfile[];
  /** Quanto do interesse do aluno é permanente, de 0 a 1 — a fração da
   * variância que não é resorteada a cada período. 0 reproduz o modelo
   * anterior; 1 congela o interesse. Ortogonal ao σ: a divisão preserva a dispersão de
   * cada período, e o que isto controla é só a correlação entre semestres. */
  interest_stability: number;
  /** Quanto do interesse é comum às turmas da **mesma disciplina**, de 0 a 1.
   * Em 1 todas valem o mesmo para o aluno (e nenhum desvio é sorteado); em 0
   * cada turma tem valor próprio. Passa pela mesma repartição temporal que a
   * disciplina, de modo que estabilidade entre períodos igual a 1 congela
   * também as turmas. */
  class_stability: number;
  /** Os três níveis da escada de dificuldade das turmas — baixa, média e
   * alta —, multiplicadores da dificuldade declarada pela disciplina. A
   * escada reparte as turmas com tantas fáceis quantas difíceis, de modo que
   * a média geométrica fica no nível do meio. Iguais entre si, a escada está
   * desligada. */
  class_difficulty_levels: [number, number, number];
  /** μ — média do logaritmo da log-normal de onde sai o **interesse**. Não
   * mexe em alocação nenhuma: soma-se ao log de toda a linha, o que a
   * multiplica por e^μ, e a normalização desfaz o fator. Existe para a prévia
   * da log-normal fonte, que em μ = 0 se espreme entre 0 e 1. A atratividade
   * A_x de cada disciplina soma-se a ele. */
  interest_mean: number;
  /** σ — desvio do logaritmo da log-normal de onde sai o **interesse** — o
   * sorteio que, normalizado sobre a grade e visto pelo histórico do aluno,
   * vira a **utilidade**. Controla o quanto o aluno diferencia as
   * disciplinas: sigma **grande** concentra (quer uma ou duas e despreza o
   * resto), **pequeno** achata. A faixa útil cabe entre ~0,25 e ~3. */
  interest_sigma: number; // > 0
  /** W_a — carga horária máxima por período, eq. (4). Igual para todos. */
  max_hours: number;
  /** Em quantos períodos entra coorte nova, contados do primeiro. Depois do
   * último ingresso vem a drenagem: ninguém mais entra e a população só
   * diminui, o que dá às coortes tardias tempo de chegar ao fim do curso.
   * **Só há uma coorte por período com ingresso** — os de drenagem não têm
   * coorte correspondente. */
  entry_periods: number;
  /** Períodos que o aluno tem para concluir, contados do ingresso. Quem chega
   * ao fim do último sem fechar a grade é **jubilado** e sai da simulação. Com
   * `entry_periods`, fecha o ciclo de vida da população e determina |T|
   * (`horizonFor`): o motor recebe o horizonte, mas quem o escolhe são estes
   * dois. */
  max_residence: number;
  /** Exemplares de cada combinação de perfil em cada coorte. A coorte é isto
   * vezes o número de combinações, e a população é a coorte vezes os períodos
   * com ingresso.
   *
   * O tamanho da coorte não é digitado: ele é derivado, e é assim que toda
   * combinação de perfil recebe o mesmo número de exemplares em toda coorte,
   * sem sobra a girar. O bloco da coorte que cai em cada turma de entrada não
   * pode passar das vagas dela, porque o ingressante tem vaga garantida em
   * toda disciplina de entrada. */
  students_per_profile: number;
  rounds: number; // |R|
  min_grade: number; // n_min
  /** Quem decide a alocação — o segundo eixo da comparação. Cruzado com o
   * mecanismo dá as quatro células; os dois resolvedores só divergem onde a
   * carga horária aperta. */
  resolver: "ilp" | "greedy";
  /** Se o orçamento carrega entre períodos (eq. 36) ou recomeça em Γ_min. */
  credit_memory: "none" | "carry";
  /** X — carga horária optativa exigida para concluir, somada entre as
   * optativas aprovadas. Concluir é aprovar em todas as obrigatórias e chegar
   * a este total; o aluno escolhe *quais* optativas. */
  elective_hours: number;
  base_credits: number; // Γ_min
  credit_return: CreditReturnPolicy;
  seed: number;
}

/** Os dois mecanismos de alocação comparados pelo trabalho. `credits` é o
 * leilão por créditos proposto (Seção 7.1); `ranking` é a linha de base
 * tradicional, que atende as solicitações em ordem decrescente de CR
 * (Seção 7.3.1, eqs. 49-50). Espelha `leilao.config.Mechanism`. */
export type Mechanism = "credits" | "ranking";

/** Os modelos comparados, na ordem do caminho — que é também a ordem do eixo,
 * da legenda e das cores.
 *
 * O eixo é um **caminho**, e cada seta muda **uma** coisa só. É o que torna o
 * vão atribuível: comparar o CR direto com o leilão mediria mensagem e
 * resolução somadas, sem dizer qual pesou.
 *
 *     CR ──mensagem──▶ Bidding points ──resolução──▶ sem retorno ──retorno──▶ com retorno
 *
 * 1. **Mensagem**: o CR dá um número por *aluno*, o lance dá um número por
 *    *par* (aluno, disciplina). Os dois resolvem ordinalmente.
 * 2. **Resolução**: ordinal usa só a *ordem* dos lances — qualquer
 *    transformação monótona dá a mesma alocação —, cardinal usa as
 *    *magnitudes* e derruba um lance alto para acomodar dois médios.
 * 3. **Retorno**: quem aprova recupera a fatia do preço correspondente à
 *    nota. É a única fonte de mérito do leilão.
 *
 * **Só entra aqui o que sai nos resultados**: cada braço é um traçado dos
 * gráficos e uma linha das tabelas, e nada roda para não ser mostrado.
 *
 * Espelha `leilao.comparison.ARMS`; o `key` é o que casa as duas pontas. */
interface ArmDescription {
  key: string;
  label: string;
  /** Rótulo curto: em espaço apertado cabe pouco, e o nome inteiro
   * fica na legenda. */
  short: string;
  hint: string;
}

/** Os dois modelos comparados, na ordem do eixo.
 *
 * A complexidade do trabalho foi para os parâmetros — os perfis de aluno e a
 * disponibilidade —, e por equilíbrio saiu dos modelos. O preço é que o vão
 * medido soma três mudanças ao mesmo tempo (mensagem, resolução e retorno) e
 * não diz qual pesou; a escada que as separava está em `ABLATION_ARMS`.
 *
 * Espelha `leilao.comparison.ARMS`; o `key` é o que casa as duas pontas. */
export const COMPARISON_ARMS: ArmDescription[] = [
  {
    key: "ranking_greedy",
    label: "CR",
    short: "CR",
    hint: "a linha de base: matrícula por histórico. Os alunos entram em ordem decrescente de CR e cada um leva o que quer, na própria ordem de preferência, enquanto houver vaga e carga — eqs. (49)-(50). Ordinal: a alocação usa só a ordem, nunca a magnitude. Excluir não custa nada aqui — não há moeda a perder",
  },
  {
    key: "credits_return",
    label: "Leilão",
    short: "Leilão",
    hint: "o modelo proposto (Seção 7.1): o aluno reparte um orçamento de créditos em lances por disciplina, um PLI resolve a alocação e o segundo preço cobra. Com a política proporcional de f_γ (eq. 34), quem aprova recupera a fatia do preço correspondente à nota — e quem exclui recupera metade, de modo que largar vaga custa",
  },
];

/** Os dois degraus do meio do caminho, que **não** rodam por padrão.
 *
 * Separam o vão em três parcelas, e o motor os alcança por
 * `run_comparison(..., arms=ARMS + ABLATION_ARMS)`. Ficam aqui só para que o
 * traço de uma simulação antiga continue com rótulo legível. */
export const ABLATION_ARMS: ArmDescription[] = [
  {
    key: "credits_greedy",
    label: "Bidding points",
    short: "Bidding points",
    hint: "o mecanismo de pontos das business schools (Sönmez & Ünver 2010): lances repartidos de um orçamento, atendidos em ordem decrescente. Ordinal como o CR — o que muda é só a mensagem, que passa a ser um número por disciplina em vez de um por aluno",
  },
  {
    key: "credits_ilp",
    label: "Leilão sem retorno",
    short: "Sem retorno",
    hint: "o mesmo leilão resolvido por PLI, mas sem devolver crédito nenhum. Cardinal — a alocação usa as magnitudes e derruba um lance alto para acomodar dois médios. O que muda em relação ao bidding points é só a resolução",
  },
];

export const armLabel = (key: string): string =>
  [...COMPARISON_ARMS, ...ABLATION_ARMS].find((arm) => arm.key === key)?.label ?? key;

/** Uma comparação: o mesmo cenário rodado em cada modelo, N vezes.
 *
 * Dois campos do cenário não entram. A **seed**, porque as seeds são 1..N e são
 * pareadas, de modo que a i-ésima simulação de cada braço parte da mesma
 * população, das mesmas utilidades e das mesmas notas (condição metodológica da
 * Seção 7.3). E o **retorno de créditos**, porque ele é o eixo do experimento:
 * cada braço impõe o seu. */
export interface CompareRequest
  extends Omit<Scenario, "seed" | "credit_return"> {
  runs: number; // N
  /** Quais braços rodar, pelas chaves de `COMPARISON_ARMS`. Rodar um só custa
   * metade do tempo: os painéis que comparam os dois lados somem, o resto da
   * tela desenha o que veio. Espelha `CompareRequest.arms` da API. */
  arms: string[];
}

/** Teto de simulações por mecanismo. Espelha `leilao.comparison.MAX_RUNS`. */
export const MAX_COMPARISON_RUNS = 100;

/** As métricas de período de uma simulação, sem reduzir — o que o recorte por
 * período desenha.
 *
 * Listas **paralelas**, e só com os períodos medidos: `period[i]` é o número do
 * período a que `efficiency[i]` se refere. O primeiro período não aparece (nele
 * todo mundo acabou de ingressar e não há o que medir), e por isso o número do
 * período vem explícito em vez de sair do índice.
 *
 * `students` é o peso daquele ponto na média ponderada que produz o `RunSummary`
 * — e é o que cai à vista na drenagem.
 *
 * Sem tempo de formatura: ele é da simulação inteira, e a versão por período
 * ("quanto levou quem concluiu em t") seria outra grandeza, com viés de
 * sobrevivência. */
export interface PeriodSeries {
  period: number[];
  students: number[];
  efficiency: number[];
  utilization: number[];
  fidelity: number[];
  fairness: number[];
  correlation: number[];
  exclusion_rate: number[];
  /** A série da seção "Solicitações de disciplinas": seis linhas **não
   * empilhadas**, em média por aluno, uma posição por período medido.
   *
   * Não empilhadas porque empilhar torna a espessura de uma faixa legível mas
   * a posição dela dependente de tudo o que está embaixo — e comparar a linha
   * de exclusão entre dois braços com a base balançando é das leituras mais
   * difíceis que existem. Cada estado ganha escala própria pelo mesmo motivo:
   * "não elegível" gira numa ordem de grandeza e "excluída" em outra. */
  request_states: RequestStates[];
  /** A saturação do período, rodada a rodada: `allocations_per_round[i][r]` é o
   * que foi ganho por aluno na rodada r+1 do período `period[i]`. Uma linha por
   * período medido, sempre com |R| posições — lê-se por **coluna**: a 1ª rodada
   * de cada período, a 2ª de cada período, e assim por diante. */
  allocations_per_round: (number | null)[][];
}

/** Uma simulação reduzida a um ponto por métrica — o que vira um valor dentro
 * das tabelas. As três de período são a média **ponderada pelos alunos
 * medidos**: a simulação termina numa fase de drenagem, e uma média simples
 * daria a um período final de vinte alunos o mesmo peso de um período cheio. O
 * tempo de formatura não é de período — é da simulação inteira. */
export interface RunSummary {
  seed: number;
  /** Períodos efetivamente publicados; menor que |T| se a população se
   * esvaziou antes do horizonte. */
  periods: number;
  /** Concluintes da simulação. Não é métrica: é o denominador sem o qual
   * `time_to_graduate` não se lê — quem forma menos gente pode exibir um tempo
   * menor só porque sobraram os rápidos. */
  graduates: number;
  /** Jubilados da simulação: esgotaram a residência sem fechar a grade. */
  dismissed: number;
  /** Quantos ingressaram ao todo — o denominador das duas frações. */
  population: number;
  efficiency: number; // ψ̄ — eq. (53)
  /** Aproveitamento: carga horária obtida ÷ W_a. A contraparte em carga do ψ,
   * que é em utilidade — as duas se separam onde está a patologia que
   * interessa. */
  utilization: number;
  /** Fidelidade da mensagem: quanto da preferência sobrevive à tradução para
   * o que o mecanismo de fato recebe. **Descreve, não pontua.** */
  fidelity: number;
  fairness: number; // φ — eq. (55)
  correlation: number; // λ — eq. (57)
  /** Desperdício: a fração das vagas obtidas que foi largada antes de virar
   * aula. É a quinta métrica da comparação, e a que a disponibilidade existe
   * para produzir. */
  exclusion_rate: number;
  /** Os seis estados em média por aluno, reduzidos a um ponto cada. A série
   * por período está em `ArmResult.series`. */
  request_states: RequestStates;
  /** Períodos do ingresso ao diploma, na média dos concluintes; conta o período
   * da formatura. `null` quando ninguém concluiu — zero ali se leria como
   * "formou na hora". */
  time_to_graduate: number | null;
  /** Vagas obtidas por aluno **em cada rodada**, na ordem delas: o índice r-1 é
   * a rodada r, e há |R| posições. Mede a **saturação da demanda** — o que se
   * lê é o decaimento entre as rodadas, não o nível de cada uma.
   *
   * Conta o que foi ganho *naquela* rodada, não o acumulado, então as posições
   * somadas dão as vagas por aluno do período. E, como o calouro está fora do
   * recorte, a matrícula garantida não infla a primeira. */
  allocations_per_round: (number | null)[];
  /** A série por período desta simulação. Só existe em comparação gravada
   * antes de 09/11/2026, quando a redução entre seeds era feita na tela; hoje
   * a API manda `ArmResult.series` já reduzida. É dela que sai o recorte
   * "Geral" dessas comparações antigas (`legacyBands`), e só na régua do
   * período: as outras duas precisam das células, que ali não foram gravadas. */
  by_period?: PeriodSeries;
}

/** Um dos modelos comparados e as suas N simulações. O rótulo em português está
 * em `COMPARISON_ARMS`, casado por `key`; a API manda só o identificador e o
 * que define o braço. */
export interface ArmResult {
  key: string;
  mechanism: Mechanism;
  credit_return: CreditReturnPolicy;
  runs: RunSummary[];
  /** As séries reduzidas entre as seeds: cada régua do eixo X cruzada com o
   * agregado e com cada recorte. Ausente em comparação gravada antes de
   * 09/11/2026; sem `ruler` nas gravadas antes de 11/11/2026. */
  series?: AxisBands[];
}

/** Os recortes **espaciais** da tela de comparação — as cores das linhas.
 * `overall` é a universidade inteira, um grupo só; os outros quatro são os
 * eixos de perfil.
 *
 * A coorte saiu daqui e virou régua (`Ruler`): ela é um corte do tempo, e
 * tê-la como cor obrigava a ler duas dimensões temporais no mesmo gráfico. */
export type CutAxis =
  | "overall"
  | "performance"
  | "availability"
  | "selectivity"
  | "concentration";

/** As réguas do eixo X — `leilao.comparison.RULERS`.
 *
 * - `period` é o calendário da universidade: é onde se veem as três fases do
 *   horizonte, e cada ponto tem uma coorte diferente em cada idade.
 * - `age` é o tempo do aluno: alinha as coortes pelo ingresso e tira a fase do
 *   horizonte de dentro da curva.
 * - `cohort` é um corte transversal: um ponto por turma de ingresso, com a
 *   vida inteira dela resumida. */
export type Ruler = "period" | "age" | "cohort";

/** `[q1, mediana, q3]` entre as seeds. */
export type Band = [number, number, number];

/** Um grupo de um recorte, reduzido entre as seeds ponto a ponto da régua.
 * `values[k][i]` é a faixa da grandeza `k` no ponto `x[i]`, ou `null` se
 * nenhuma seed a mediu. `n[i]` é quantas seeds mediram o grupo ali.
 *
 * As grandezas: `students`, `graduation_rate` (acumulada), `efficiency`,
 * `utilization`, `fidelity`, `fairness`, `correlation`, `exclusion_rate`, os
 * seis estados de solicitação pelo nome, as quatro frações do funil
 * (`requested_share`, `granted_share`, `attended_share`, `approved_share`) e
 * `round_<r>` para a saturação.
 *
 * Espelha `api.schemas.GroupBandsOut`. */
export interface GroupBands {
  group: string;
  /** O ponto da régua: período, idade ou coorte, conforme o `ruler` do eixo.
   * `period` é o nome que o campo tinha até 11/11/2026, quando a régua passou
   * a ser escolha — comparação gravada antes disso traz aquele. */
  x?: number[];
  period?: number[];
  n: number[];
  values: Record<string, (Band | null)[]>;
}

/** Os grupos de um recorte espacial sob uma régua. As duas escolhas são
 * independentes na tela, e a API manda as combinações todas.
 *
 * `ruler` é ausente em comparação gravada antes de 11/11/2026, e ali vale
 * `period` — era a única régua. */
export interface AxisBands {
  ruler?: Ruler;
  axis: CutAxis;
  groups: GroupBands[];
}

export interface CompareResponse {
  /** Onde a API gravou esta execução, ou `null` se o disco recusou. */
  saved_to: string | null;
  runs: number;
  arms: ArmResult[];
  /** As duas distribuições de entrada do cenário. Não variam entre braços nem
   * entre seeds — são do cenário, não da simulação. A primeira é do
   * interesse, não da utilidade: é o que σ governa. */
  interest_distribution?: number[];
  grade_distribution?: number[];
}

/** Os seis estados de uma solicitação, em **média por aluno**.
 *
 * Particionam o que ainda falta ao aluno — o catálogo menos o que ele já
 * aprovou —, de modo que a soma é o tamanho desse denominador. A ordem dos
 * campos é a do funil, do mais distante ao mais bem-sucedido:
 *
 *     não elegível → não solicitada → indeferida → excluída → reprovada → aprovada
 *
 * **O já aprovado sai do denominador**, e isso não é detalhe: juntá-lo com o
 * bloqueado num estado só faria a mesma faixa crescer com o progresso do aluno
 * e encolher com o desbloqueio dele, e as duas se cancelariam em parte.
 *
 * É média, nunca soma: a soma seria governada pela população, que sobe no
 * escalonamento de ingresso e despenca na drenagem, e o gráfico mostraria o
 * tamanho da universidade em vez do mecanismo.
 *
 * Espelha `equations.request_states.RequestStates`. */
export interface RequestStates {
  not_eligible: number;
  not_requested: number;
  /** Pediu e não foi atendido. "Indeferida" na tela, para não se confundir
   * com "reprovada" de relance; a chave é a da API. */
  refused: number;
  excluded: number;
  failed: number;
  approved: number;
}

export interface Metrics {
  students: number;
  allocated: number;
  allocations_per_student: number;
  /** ψ̄ — eq. (53): a soma das utilidades atendidas. A linha é normalizada
   * sobre a grade, então o denominador vale 1 e ψ é a fração do desejo
   * **total** do aluno que foi servida — não do que estava ao alcance dele.
   * ψ = 1 exigiria cursar a grade inteira num período. */
  efficiency: number;
  /** Aproveitamento — carga horária obtida no período ÷ W_a, média dos alunos
   * medidos. É a contraparte em **carga** do ψ, que é em **utilidade**: o
   * aluno que concentra o lance, ganha a disciplina que amava e deixa o resto
   * de W_a ocioso pontua ψ alto e aproveitamento baixo. Em [0, 1]. */
  utilization: number;
  /** Fidelidade da mensagem — o cosseno entre o vetor de lances normalizado e
   * o de utilidades, sobre o elegível. O mecanismo nunca vê `u`: vê a
   * mensagem, e isto mede quanto da preferência sobrevive à tradução. A linha
   * de base só diz um conjunto (peso uniforme); o leilão diz o quanto.
   * **Descreve, não pontua.** O piso é 1/√n, então compare braços dentro do
   * mesmo período. */
  fidelity: number;
  fairness: number; // φ — Jain, eq. (55)
  occupancy: number; // θ — eq. (54)
  /** Vagas que o recorte obteve e largou. `null` em plena rodada: a exclusão
   * acontece depois da última, então só o fim do período tem o que contar. */
  excluded: number | null;
  /** Desperdício: as vagas excluídas sobre as obtidas. É a diferença entre as
   * duas leituras de ocupação — a vaga saiu da oferta de qualquer jeito, mas
   * só a parte retida virou carga cursada. */
  exclusion_rate: number | null;
  /** Aproveitamento **efetivo**: carga retida ÷ W_a. Lido contra
   * `utilization`, que fica no alocado, o vão entre os dois é o desperdício.
   *
   * A divisão de trabalho é essa: as grandezas de **contagem** (allocated,
   * occupancy, utilization) ficam no alocado, porque a vaga saiu do sistema
   * tenha sido cursada ou não; as de **valor** (efficiency, fairness,
   * correlation) ficam no retido, porque o aluno não consumiu a utilidade do
   * que largou. */
  effective_utilization: number | null;
  /** Os seis estados de solicitação, em média por aluno — a seção
   * "Solicitações de disciplinas". */
  request_states: RequestStates | null;
  /** Escassez: elegíveis por vaga. Para cada disciplina que o aluno ainda pode
   * cursar — não aprovada e com os pré-requisitos cumpridos —, (quantos são
   * elegíveis a ela) ÷ (vagas); a do aluno é a média dessas razões, e a do
   * recorte é a média dos alunos. Demanda **potencial** — mesma unidade e mesma
   * forma da concorrência, que mede a efetiva. */
  scarcity: number;
  /** Concorrência: solicitantes por vaga. Mesma forma da escassez sobre as
   * disciplinas em que o aluno deu lance, contando quem deu lance em cada uma.
   * A matrícula garantida conta como pedido: o ingressante não disputou, mas
   * ocupa a vaga. Demanda **efetiva**: a razão concorrência ÷ escassez diz
   * quanto da demanda potencial virou pedido. */
  contention: number;
  mean_grade_average: number; // N̄ — eq. (56)
  correlation: number; // λ — eq. (57)
  /** Carga horária aprovada ÷ (W_a × idade em períodos), média do recorte.
   * Não está no anteprojeto: mede o atraso na progressão na grade. */
  semestralization: number;
}

/** Um recorte de alunos num instante: a universidade inteira (`overall`) ou uma
 * coorte (`by_cohort`). Os dois trazem os mesmos campos, então um gráfico só
 * troca de lista para trocar de agregação. */
export interface GroupSnapshot {
  /** Quem é este recorte: `null` na universidade inteira e o período de
   * ingresso (t_a, eq. 31) em `by_cohort`. Texto, e não número, porque o eixo é
   * genérico; a lista de origem diz como ler a chave. */
  group: string | null;
  /** Nulos quando o recorte não tem aluno no período: não havia ninguém, o que
   * é diferente de ninguém ter ficado satisfeito. Zero seria um ponto falso. */
  metrics: Metrics | null;
  active: number;
  /** Alunos do recorte que já ingressaram, tenham concluído ou não. **Não** é
   * `active + graduated`: quem se forma ao fim do período conta nos dois lados
   * dessa soma, porque disputou o período inteiro antes de sair. É este o
   * denominador da fração de formados. */
  population: number;
  graduated: number;
  /** Jubilados acumulados. Com `graduated`, reparte `population` em três: quem
   * saiu por cima, quem saiu por baixo e quem ainda disputa. As duas frações
   * só somam 1 no fim do horizonte. */
  dismissed: number;
  mean_credits: number | null;
  mean_approved_hours: number | null;
  /** Oferta de créditos do início do período (C_a^(t,1), antes dos lances),
   * dividida pelos alunos do recorte e pelas vagas de toda a universidade — a
   * segunda é o preço que uma vaga teria se todo o crédito fosse gasto. */
  credits_per_student: number | null;
  credits_per_seat: number | null;
  /** Créditos apostados no período por aluno ativo, somando as rodadas.
   * **Pode passar do orçamento**: lance perdido não consome nada (eq. 25),
   * então o crédito que não virou vaga volta a ser apostado na rodada
   * seguinte. O vão até o gasto é o que foi comprometido e não pago. */
  mean_bids: number | null;
  /** Retorno de créditos do período por aluno ativo (Σγ, eq. 34). `null` nas
   * rodadas: em plena rodada as notas ainda não saíram, e 0 ali se leria como
   * "a política não devolveu nada". */
  mean_credit_return: number | null;
}

/** Dispersão do preço de mercado (π_x, eq. 24) entre as disciplinas que
 * estavam no mercado no instante — as que ainda tinham vaga. O preço não é
 * grandeza de aluno nem de coorte: é o que a faixa entre a disciplina mais
 * cara e a mais barata diz sobre onde o crédito se concentrou. */
export interface PriceStats {
  min: number;
  mean: number;
  max: number;
}

export interface RoundReport {
  period: number;
  round: number; // 0 = agregado do período
  /** Toda a universidade. */
  overall: GroupSnapshot;
  /** O mesmo instante agregado por coorte. Só as coortes que já ingressaram,
   * então a série de uma coorte começa no período do seu ingresso — e o aluno
   * fica na mesma coorte do início ao fim. */
  by_cohort: GroupSnapshot[];
  /** `null` quando nenhuma disciplina estava no mercado: sem oferta não há
   * preço, e 0 ali se leria como "de graça". */
  prices: PriceStats | null;
}

export interface DisciplineSnapshot {
  /** O nome da **turma**: é dela que são a vaga, o preço e a demanda. Com
   * turma única ele é o da disciplina, e era esse o modelo até elas
   * existirem. */
  name: string;
  /** O clique a que a turma pertence — por onde a tela agrupa. */
  discipline: string;
  /** Os três eixos pelos quais as disciplinas se agrupam nos gráficos. O
   * período vem dos pré-requisitos; vagas e carga horária são do cenário, e
   * disciplinas com o mesmo valor caem no mesmo grupo. */
  curriculum_period: number;
  hours: number;
  seats: number;
  filled: number;
  /** Vagas entregues à matrícula garantida dos ingressantes, antes do leilão.
   * Só é diferente de zero nas disciplinas de entrada. */
  granted: number;
  /** Quantos alunos pediram a disciplina no período — deram lance em alguma
   * rodada, ou a receberam na matrícula garantida. Dividido por `seats` dá a
   * **concorrência** dela: candidatos por vaga. */
  requests: number;
  /** Média de π_x nas rodadas em que a disciplina ainda tinha vaga. `null` se
   * ela nunca esteve no mercado — a esgotada não vale o piso da eq. (24), que
   * leria como barata justamente a que todo mundo quis. */
  mean_price: number | null;
  approvals: number;
  /** Vagas desta disciplina obtidas e depois largadas. Com `filled`, separa a
   * vaga que virou aula da que só saiu da oferta. */
  exclusions: number;
}

export interface PeriodReport {
  period: number;
  rounds: RoundReport[];
  aggregate: RoundReport;
  disciplines: DisciplineSnapshot[];
  graduated_now: number;
  dismissed_now: number;
}

export interface StudentSummary {
  id: string;
  name: string;
  entry_period: number; // t_a — eq. (31)
  /** Os quatro grupos a que ele pertence, pelo nome. Os dois primeiros são
   * **traço** e não entram em decisão nenhuma dele; os dois últimos são
   * **estratégia** e são exatamente o que ele decide. Estão aqui porque a tela
   * individual é onde se pergunta "por que *este* aluno foi assim" — e o
   * perfil é metade da resposta, com a seed sendo a outra. */
  performance: string;
  availability: string;
  selectivity: string;
  concentration: string;
  grade_average: number; // N_a — eq. (49)
  approved_hours: number;
  /** S — a carga da grade inteira. Toda disciplina é obrigatória, então é a
   * mesma meta para todos. */
  hours_to_graduate: number;
  credits: number;
  enrollments: number;
  approvals: number;
  mean_satisfaction: number;
  /** Período em que concluiu o curso — a **única** porta de saída. Quem não
   * concluiu continua disputando até o fim do horizonte. */
  graduated_at: number | null;
  dismissed_at: number | null;
}

/** Rodada de `won_round` quando a vaga não veio de rodada nenhuma: é a
 * matrícula garantida do ingressante, concedida antes de o leilão abrir. */
export const GUARANTEED_ROUND = 0;

/** O que aconteceu com uma disciplina que o aluno quis num período.
 * `bids` todo zero = o aluno nem chegou a dar lance (a disciplina saiu de
 * B_a^(t,r): sem vaga, sem carga horária ou sem orçamento). */
export interface RequestRecord {
  discipline: string;
  utility: number; // ũ_{a,x}^(t) — a utilidade, não o interesse
  bids: number[]; // créditos apostados em cada rodada
  /** Rodada em que obteve a vaga; `null` = indeferida. `GUARANTEED_ROUND` (0) é a
   * matrícula garantida do ingressante. */
  won_round: number | null;
  paid: number; // eq. (27)
  /** Obteve a vaga e não cursou: a disponibilidade do período não comportou.
   * Com ela, `attempt` e `grade` vêm `null` — não houve tentativa — e
   * `returned` traz metade do preço pago em vez do retorno por nota. */
  excluded: boolean;
  attempt: number | null;
  grade: number | null; // eq. (33)
  approved: boolean;
  returned: number; // γ_{a,x} — créditos devolvidos por ela, eq. (34)
}

export interface StudentPeriodRecord {
  period: number;
  credits_start: number;
  credits_spent: number;
  credits_returned: number; // Σγ do período — eq. (35), sem o Γ_min
  credits_end: number;
  satisfaction: number; // psi_a^(t) — eq. (51)
  grade_average: number; // CR no início do período — eq. (49)
  approved_hours: number;
  /** Carga obtida no período, **antes** de excluir. */
  enrolled_hours: number;
  /** Carga que ele de fato cursou e o teto que a disponibilidade lhe deu:
   * `retained_hours <= effective_load`, e o vão para `enrolled_hours` é o que
   * ele largou. */
  retained_hours: number;
  effective_load: number;
  requests: RequestRecord[];
  graduated: boolean;
}

export interface StudentHistory {
  student_id: string;
  periods: StudentPeriodRecord[];
}

/** O pedido do traço de **uma** simulação da comparação: o cenário dela mais o
 * par `(braço, seed)` que endereça a simulação.
 *
 * Aqui a seed não é ignorada como em `/compare` — ela é o que se pede. E o
 * retorno de créditos e o resolvedor continuam de fora: quem os impõe é o
 * braço, que é o que faz o traço ser a mesma simulação que a comparação resumiu. */
export interface TraceRequest extends Omit<Scenario, "seed" | "credit_return"> {
  arm: string;
  seed: number;
}

/** O contexto de mercado de um período: a oferta disciplina a disciplina. É o
 * que a vista por disciplina lê no cabeçalho de cada período. */
export interface TracePeriod {
  period: number;
  disciplines: DisciplineSnapshot[];
}

/** Uma simulação inteira, aluno a aluno — a tela de depuração do projeto.
 *
 * É a parte pesada do resultado (uns 10 MB no preset Computação, contra uns
 * 450 kB do resumo da comparação), e por isso **não** é persistida no histórico
 * nem vem junto de `/compare`: quem quer o caso individual o pede, e só
 * daquela simulação. A simulação é determinística, então refazê-la custa tempo
 * e não fidelidade. */
export interface TraceResponse {
  arm: string;
  seed: number;
  periods: TracePeriod[];
  students: StudentSummary[];
  /** Detalhe período a período de cada aluno, com uma linha por disciplina
   * elegível — inclusive as que ele nem chegou a pedir. */
  histories: StudentHistory[];
  /** As **turmas** ofertadas, na ordem da grade: são elas que a tela
   * endereça, porque é delas que são o lance e a vaga. */
  disciplines: string[];
  /** Turma → disciplina. É por aqui que a tela volta ao clique para achar o
   * período da grade e saber se é optativa, que são coisas da disciplina. */
  classes: Record<string, string>;
  /** Período de cada disciplina na grade, induzido dos pré-requisitos. */
  curriculum_periods: Record<string, number>;
}

export interface PlaygroundRequest {
  mechanism: Mechanism;
  rounds: number;
  seed: number;
  mode_grade: number;
  zero_rate: number;
  max_rate: number;
  /** Turmas: o bem alocado. `discipline` é o clique — ninguém leva duas. */
  classes: { name: string; discipline: string; seats: number; hours: number }[];
  students: {
    id: string;
    credits: number;
    cr: number;
    max_hours: number;
    utilities: Record<string, number>;
    eligible: string[];
    /** Horas já realizadas; ausente, o aluno leva tudo o que obteve. */
    availability?: number;
    selectivity: number;
    concentration: number;
  }[];
}

export interface PlaygroundRoundStudent {
  id: string;
  bids: Record<string, number>;
  utilities: Record<string, number>;
  won: string[];
  remaining_hours: number;
  remaining_credits: number | null;
}

export interface PlaygroundRound {
  number: number;
  prices: Record<string, number> | null;
  students: PlaygroundRoundStudent[];
}

export interface PlaygroundClosing {
  student_id: string;
  /** Ŵ_a; `null` quando a disponibilidade não foi dada. */
  load: number | null;
  retained: string[];
  excluded: string[];
}

export interface PlaygroundResponse {
  rounds: PlaygroundRound[];
  closing: PlaygroundClosing[];
  /** Só do que foi cursado: a excluída não recebe nota. `name` é a turma. */
  grades: { student_id: string; name: string; grade: number }[];
}

/** |T| — o horizonte que esgota a população, dado o ciclo de vida dela.
 *
 * Espelha `config.horizon_for_lifecycle` do motor, porque a tela de
 * configuração precisa do número ao vivo, enquanto o usuário mexe nos dois
 * controles de que ele sai. O **menos um** é a sobreposição do primeiro
 * período: a coorte que entra em t = 1 já gasta ali o primeiro período de
 * residência dela.
 */
export const horizonFor = (entryPeriods: number, maxResidence: number): number =>
  entryPeriods + maxResidence - 1;
