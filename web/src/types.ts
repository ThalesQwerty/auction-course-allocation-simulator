// Espelha src/leilao/api/schemas.py

export interface DisciplineInput {
  name: string;
  seats: number; // q_x — vagas
  hours: number; // w_x — carga horária
  /** Disciplinas que o aluno precisa ter aprovado para disputar vaga aqui.
   * Vazio = disciplina de 1º período, em que o ingressante entra direto, sem
   * leilão. O período de cada disciplina sai daí por indução — ver
   * `curriculum.ts`. */
  prerequisites: string[];
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

/** Nome de uma geração — o grupo que ingressou naquele período (geração 3 =
 * quem entrou no período 3, esteja ele hoje em que semestre estiver). O aluno
 * nasce numa geração e fica nela até o fim, que é o que mantém cada série
 * falando sempre do mesmo conjunto de alunos.
 *
 * Com os cursos fora do modelo, a geração é o único recorte de aluno que
 * sobra — e é também o que mais separa as curvas, porque a posição na cadeia de
 * pré-requisitos é o que de fato distingue um aluno de outro aqui. */
export const cohortLabel = (entryPeriod: number): string => `Geração ${entryPeriod}`;

/** Perfil de aptidão: a normal das notas de primeira tentativa do aluno. É o
 * que dá heterogeneidade de desempenho — sem ela o CR vira ruído e a
 * correlação da eq. (57) não mede nada. */
export interface AptitudeProfileInput {
  name: string;
  mean: number; // média das notas, em [0, 10]
  stddev: number; // desvio padrão, > 0
  /** Quanto a nota sobe a cada recursada — eq. (33). Fica no perfil, e não no
   * cenário, porque é a mesma grandeza que a média e o desvio: o quanto o aluno
   * aprende. Um perfil que erra muito na primeira tentativa pode ser justamente
   * o que mais ganha ao repetir. */
  learning_gain: number;
  share: number; // % dos alunos com este perfil
}

/** Sentido da distorção da matriz de utilidades. `concentrated` eleva a um
 * inteiro positivo e afasta as utilidades entre si; `diluted` eleva ao inverso
 * dele e as aproxima. */
export type AffinityKind = "concentrated" | "diluted";

export const AFFINITY_KINDS: { value: AffinityKind; label: string; hint: string }[] = [
  {
    value: "concentrated",
    label: "concentrado",
    hint: "afasta as utilidades entre si — o aluno quer muito uma ou duas disciplinas",
  },
  {
    value: "diluted",
    label: "diluído",
    hint: "aproxima as utilidades — o aluno é indiferente entre o que lhe resta",
  },
];

export const affinityKindLabel = (kind: AffinityKind): string =>
  AFFINITY_KINDS.find((option) => option.value === kind)?.label ?? kind;

/** Perfil de afinidade: o quanto o aluno concentra a preferência. A utilidade
 * sorteada é elevada ao expoente do perfil e renormalizada, de modo que U_a
 * continue valendo a eq. (43). Intensidade 1 é o perfil neutro — expoente 1
 * nos dois sentidos, sem distorção alguma. */
export interface AffinityProfileInput {
  name: string;
  kind: AffinityKind;
  intensity: number; // inteiro positivo, até MAX_AFFINITY_INTENSITY
  /** W_a — carga horária máxima por período, eq. (4). Fica no perfil porque
   * anda junto da concentração: quem quer poucas disciplinas com intensidade e
   * quem quer muitas por igual não descrevem só preferência, mas também quanto
   * conseguem carregar num período. */
  max_hours: number;
  share: number; // % dos alunos com este perfil
}

/** Acima disso a transformação não muda mais nada de útil: com expoente 10 a
 * massa já está praticamente toda na disciplina preferida. Espelha
 * `leilao.config.MAX_AFFINITY_INTENSITY`. */
export const MAX_AFFINITY_INTENSITY = 10;

/** O expoente que o perfil aplica a u_{a,x} — espelha `AffinityProfile.exponent`. */
export const affinityExponent = (profile: AffinityProfileInput): number =>
  profile.kind === "concentrated" ? profile.intensity : 1 / profile.intensity;

export interface SimulateRequest {
  disciplines: DisciplineInput[];
  /** Os dois eixos de perfil do aluno. São **independentes**: a fatia de cada
   * perfil de aptidão é a mesma dentro de cada perfil de afinidade, então a
   * fatia de uma combinação é o produto das duas (dois perfis de 50% em cada
   * eixo dão 25% para cada uma das quatro combinações). As fatias de cada eixo
   * somam 100%. */
  aptitude_profiles: AptitudeProfileInput[];
  affinity_profiles: AffinityProfileInput[];
  periods: number; // |T|
  /** L — em quantos dos |T| períodos entra geração nova, contados do primeiro.
   * `null` = em todos. Com L < |T| há uma fase de drenagem depois do último
   * ingresso: ninguém mais entra e a população só diminui, o que dá às gerações
   * tardias tempo de chegar ao fim do curso em vez de serem cortadas pelo
   * horizonte. **Só existem L gerações** — os períodos de drenagem não têm
   * geração correspondente. */
  entry_periods: number | null;
  /** Alunos que ingressam em cada período com ingresso; a população é isto × L.
   * Não pode passar da menor oferta entre as disciplinas de 1º período, porque
   * o ingressante tem **vaga garantida** em todas elas. */
  students_per_period: number;
  rounds: number; // |R|
  min_grade: number; // n_min
  base_credits: number; // Γ_min
  credit_return: CreditReturnPolicy;
  seed: number;
}

/** Os dois mecanismos de alocação comparados pelo trabalho. `credits` é o
 * leilão por créditos proposto (Seção 7.1); `ranking` é a linha de base
 * tradicional, que atende as solicitações em ordem decrescente de CR
 * (Seção 7.3.1, eqs. 49-50). Espelha `leilao.config.Mechanism`. */
export type Mechanism = "credits" | "ranking";

/** Os três modelos comparados, na ordem em que entram no eixo e na legenda.
 *
 * O leilão entra **duas vezes**, com e sem retorno de créditos, porque o
 * retorno é o que pode devolver ao mecanismo algum senso meritocrático: na
 * política proporcional o aluno recupera a fatia do preço correspondente à
 * nota, então ir bem compra poder de compra no período seguinte. A ordenação
 * por CR faz isso por construção — o histórico *é* o critério — e o leilão sem
 * retorno não faz de jeito nenhum. Nessa ordem, a correlação (λ) se lê de uma
 * vez: do mecanismo em que o CR decide tudo ao que o ignora, com o retorno no
 * meio.
 *
 * Espelha `leilao.comparison.ARMS`; o `key` é o que casa as duas pontas. */
export const COMPARISON_ARMS: {
  key: string;
  label: string;
  /** Rótulo do eixo do boxplot: embaixo da caixa cabe pouco — com três caixas,
   * menos ainda —, e o nome inteiro fica na legenda. */
  short: string;
  hint: string;
}[] = [
  {
    key: "ranking",
    label: "CR (legado)",
    short: "CR",
    hint: "as solicitações são atendidas em ordem decrescente do CR do aluno; a carga horária faz o papel do orçamento — eqs. (49)-(50)",
  },
  {
    key: "credits_return",
    label: "Créditos com retorno",
    short: "c/ retorno",
    hint: "o leilão com f_γ proporcional: quem aprova recupera a fatia do preço correspondente à nota, então ir bem compra poder de compra no período seguinte",
  },
  {
    key: "credits",
    label: "Créditos sem retorno",
    short: "s/ retorno",
    hint: "o leilão puro: o crédito gasto sai do sistema, e a única entrada é o Γ_min de cada período — Seção 7.1",
  },
];

export const armLabel = (key: string): string =>
  COMPARISON_ARMS.find((arm) => arm.key === key)?.label ?? key;

/** Uma comparação: o mesmo cenário rodado nos três modelos, N vezes em cada um.
 *
 * Dois campos do cenário não entram. A **seed**, porque as seeds são 1..N e são
 * pareadas, de modo que a i-ésima execução de cada braço parte da mesma
 * população, das mesmas utilidades e das mesmas notas (condição metodológica da
 * Seção 7.3). E o **retorno de créditos**, porque ele é o eixo do experimento:
 * cada braço impõe o seu. */
export interface CompareRequest
  extends Omit<SimulateRequest, "seed" | "credit_return"> {
  runs: number; // N
}

/** Teto de execuções por mecanismo. Espelha `leilao.comparison.MAX_RUNS`. */
export const MAX_COMPARISON_RUNS = 100;

/** Uma execução reduzida a um ponto por métrica — o que vira um valor dentro
 * de uma caixa. As três de período são a média **ponderada pelos alunos
 * medidos**: a simulação termina numa fase de drenagem, e uma média simples
 * daria a um período final de vinte alunos o mesmo peso de um período cheio. O
 * tempo de formatura não é de período — é da execução inteira. */
export interface RunSummary {
  seed: number;
  /** Períodos efetivamente publicados; menor que |T| se a população se
   * esvaziou antes do horizonte. */
  periods: number;
  /** Concluintes da execução. Não é métrica: é o denominador sem o qual
   * `time_to_graduate` não se lê — quem forma menos gente pode exibir um tempo
   * menor só porque sobraram os rápidos. */
  graduates: number;
  efficiency: number; // ψ̄ — eq. (53)
  fairness: number; // φ — eq. (55)
  correlation: number; // λ — eq. (57)
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
}

/** Um dos modelos comparados e as suas N execuções. O rótulo em português está
 * em `COMPARISON_ARMS`, casado por `key`; a API manda só o identificador e o
 * que define o braço. */
export interface ArmResult {
  key: string;
  mechanism: Mechanism;
  credit_return: CreditReturnPolicy;
  runs: RunSummary[];
}

/** As amostras dos três braços, pareadas pela seed: o i-ésimo elemento de cada
 * lista é a mesma população sob regras diferentes. */
export interface CompareResponse {
  runs: number;
  arms: ArmResult[];
}

export interface Metrics {
  students: number;
  allocated: number;
  allocations_per_student: number;
  /** ψ̄ — eq. (53). A utilidade do aluno é zero fora do conjunto elegível, então
   * ψ é a fração do que ele **podia** cursar e conseguiu: 1 é atingível, e é o
   * que o ingressante com matrícula garantida obtém. */
  efficiency: number;
  fairness: number; // φ — Jain, eq. (55)
  occupancy: number; // θ — eq. (54)
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

/** Um recorte de alunos num instante: a universidade inteira (`overall`), uma
 * geração (`by_cohort`) ou um perfil (`by_aptitude`, `by_affinity`). Todos
 * trazem os mesmos campos, então um gráfico só troca de lista para trocar de
 * agregação. */
export interface GroupSnapshot {
  /** Quem é este recorte: `null` na universidade inteira, o período de ingresso
   * (t_a, eq. 31) em `by_cohort` e o nome do perfil nos outros dois. Texto
   * porque os três eixos dividem a mesma estrutura; a lista de origem diz como
   * ler a chave. */
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
 * grandeza de aluno nem de geração: é o que a faixa entre a disciplina mais
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
  /** O mesmo instante agregado por geração. Só as gerações que já ingressaram,
   * então a série de uma geração começa no período do seu ingresso — e o aluno
   * fica na mesma geração do início ao fim. */
  by_cohort: GroupSnapshot[];
  /** E pelos dois eixos de perfil, na ordem em que o cenário os declara. Os
   * três recortes particionam a mesma população de formas diferentes: somar
   * qualquer um deles reproduz `overall`. */
  by_aptitude: GroupSnapshot[];
  by_affinity: GroupSnapshot[];
  /** `null` quando nenhuma disciplina estava no mercado: sem oferta não há
   * preço, e 0 ali se leria como "de graça". */
  prices: PriceStats | null;
}

export interface DisciplineSnapshot {
  name: string;
  /** Os três eixos pelos quais as disciplinas se agrupam nos gráficos. O
   * período vem dos pré-requisitos; vagas e carga horária são do cenário, e
   * disciplinas com o mesmo valor caem no mesmo grupo. */
  curriculum_period: number;
  hours: number;
  seats: number;
  filled: number;
  /** Vagas entregues à matrícula garantida dos ingressantes, antes do leilão.
   * Só é diferente de zero nas disciplinas de 1º período. */
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
}

export interface PeriodReport {
  period: number;
  rounds: RoundReport[];
  aggregate: RoundReport;
  disciplines: DisciplineSnapshot[];
  graduated_now: number;
}

export interface StudentSummary {
  id: string;
  name: string;
  entry_period: number; // t_a — eq. (31)
  aptitude: string; // nome do perfil de aptidão
  affinity: string; // nome do perfil de afinidade
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
}

/** Rodada de `won_round` quando a vaga não veio de rodada nenhuma: é a
 * matrícula garantida do ingressante, concedida antes de o leilão abrir. */
export const GUARANTEED_ROUND = 0;

/** O que aconteceu com uma disciplina que o aluno quis num período.
 * `bids` todo zero = o aluno nem chegou a dar lance (a disciplina saiu de
 * B_a^(t,r): sem vaga, sem carga horária ou sem orçamento). */
export interface RequestRecord {
  discipline: string;
  utility: number; // u_{a,x}^(t) — eq. (41)
  bids: number[]; // créditos apostados em cada rodada
  /** Rodada em que obteve a vaga; `null` = recusada. `GUARANTEED_ROUND` (0) é a
   * matrícula garantida do ingressante. */
  won_round: number | null;
  paid: number; // eq. (27)
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
  enrolled_hours: number;
  requests: RequestRecord[];
  graduated: boolean;
}

export interface StudentHistory {
  student_id: string;
  periods: StudentPeriodRecord[];
}

export interface SimulateResponse {
  periods: PeriodReport[];
  students: StudentSummary[];
  /** Detalhe período a período de cada aluno. Pesado (≈1 MB num cenário de 8
   * períodos), então não vai para o localStorage — ver `history.ts`. */
  histories: StudentHistory[];
  disciplines: string[];
  /** Período de cada disciplina na grade, induzido dos pré-requisitos. */
  curriculum_periods: Record<string, number>;
  /** Os perfis do cenário, na ordem em que `by_aptitude` e `by_affinity` saem. */
  aptitude_profiles: string[];
  affinity_profiles: string[];
}

export function defaultScenario(): SimulateRequest {
  return {
    disciplines: [],
    aptitude_profiles: [
      { name: "Padrão", mean: 6.5, stddev: 1.5, learning_gain: 2.5, share: 100 },
    ],
    affinity_profiles: [
      { name: "Padrão", kind: "concentrated", intensity: 1, max_hours: 360, share: 100 },
    ],
    periods: 1,
    entry_periods: null,
    students_per_period: 1,
    rounds: 1,
    min_grade: 5,
    base_credits: 10,
    credit_return: "none",
    seed: 0,
  };
}
