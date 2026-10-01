// Espelha src/leilao/api/schemas.py

export interface DisciplineInput {
  name: string;
  seats: number; // q_x — vagas
  hours: number; // w_x — carga horária
}

export interface CourseInput {
  name: string;
  /** Alunos que ingressam a cada período **com ingresso**: o curso recebe uma
   * geração nova em cada um dos L primeiros períodos, então sua população é
   * este número × L (`entry_periods ?? periods`), não × `periods`. */
  students_per_generation: number;
  hours_to_graduate: number; // S_k — eq. (39)
  required: string[]; // M_k — obrigatórias
  electives: string[]; // O_k — optativas
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

export interface SimulateRequest {
  disciplines: DisciplineInput[];
  courses: CourseInput[];
  periods: number; // |T|
  /** L — em quantos dos |T| períodos entra geração nova, contados do primeiro.
   * `null` = em todos. Com L < |T| há uma fase de drenagem depois do último
   * ingresso: ninguém mais entra e a população só diminui, o que dá às gerações
   * tardias tempo de chegar ao fim do curso em vez de serem cortadas pelo
   * horizonte. **Só existem L gerações** — os períodos de drenagem não têm
   * geração correspondente. */
  entry_periods: number | null;
  /** T_max — períodos que o aluno pode permanecer antes de ser jubilado por
   * decurso de prazo. **0 desliga a regra**: o jubilamento é opcional, e
   * permanecer zero períodos não significaria nada, então o valor fica livre
   * para servir de sentinela. Global, não por aluno. */
  max_residence: number;
  rounds: number; // |R|
  min_grade: number; // n_min
  base_credits: number; // Γ_min
  max_hours: number; // W_a
  learning_gain: number; // ganho de nota por recursada — eq. (33)
  credit_return: CreditReturnPolicy;
  seed: number;
}

export interface Metrics {
  students: number;
  allocated: number;
  allocations_per_student: number;
  efficiency: number; // ψ̄ — eq. (53)
  fairness: number; // φ — Jain, eq. (55)
  occupancy: number; // θ — eq. (54)
  /** Escassez: elegíveis por vaga. Para cada disciplina que o aluno ainda pode
   * cursar, (quantos são elegíveis a ela) ÷ (vagas); a do aluno é a média
   * dessas razões, e a do recorte é a média dos alunos. Demanda **potencial** —
   * mesma unidade e mesma forma da concorrência, que mede a efetiva. */
  scarcity: number;
  /** Concorrência: solicitantes por vaga. Mesma forma da escassez sobre as
   * disciplinas em que o aluno deu lance, contando quem deu lance em cada uma.
   * Demanda **efetiva**: a razão concorrência ÷ escassez diz quanto da demanda
   * potencial virou pedido. */
  contention: number;
  mean_grade_average: number; // N̄ — eq. (56)
  correlation: number; // λ — eq. (57)
  /** Carga horária aprovada ÷ (W_a × idade em períodos), média do recorte.
   * Não está no anteprojeto: mede o atraso na progressão do curso. */
  semestralization: number;
}

export interface CourseSnapshot {
  course: string;
  /** `null` no recorte do curso inteiro (`by_course`); em `by_cohort`, o
   * período de ingresso (t_a, eq. 31) da geração agregada ali. Os dois recortes
   * têm os mesmos campos, então um gráfico só troca de lista para trocar de
   * agregação. */
  entry_period: number | null;
  /** Nulos quando o recorte não tem aluno no período: não havia ninguém, o que
   * é diferente de ninguém ter ficado satisfeito. Zero seria um ponto falso. */
  metrics: Metrics | null;
  active: number;
  /** Alunos do recorte que já ingressaram, tenham saído ou não. **Não** é
   * `active + graduated + dismissed`: quem sai ao fim do período conta nos dois
   * lados dessa soma, porque disputou o período inteiro antes de sair. É este o
   * denominador das frações de formados e de jubilados. */
  population: number;
  graduated: number;
  /** Jubilados acumulados até aqui — desligados por decurso de prazo. */
  dismissed: number;
  mean_credits: number | null;
  mean_approved_hours: number | null;
  /** Oferta de créditos do início do período (C_a^(t,1), antes dos lances),
   * dividida pelos alunos do curso e pelas vagas de toda a universidade — a
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
 * grandeza de aluno nem de curso: é o que a faixa entre a disciplina mais cara
 * e a mais barata diz sobre onde o crédito se concentrou. */
export interface PriceStats {
  min: number;
  mean: number;
  max: number;
}

export interface RoundReport {
  period: number;
  round: number; // 0 = agregado do período
  overall: Metrics;
  by_course: CourseSnapshot[];
  /** O mesmo instante agregado por curso × geração. Só as gerações que já
   * ingressaram, então a série de uma geração começa no período do seu
   * ingresso — e o aluno fica na mesma geração do início ao fim. */
  by_cohort: CourseSnapshot[];
  /** `null` quando nenhuma disciplina estava no mercado: sem oferta não há
   * preço, e 0 ali se leria como "de graça". */
  prices: PriceStats | null;
}

export interface DisciplineSnapshot {
  name: string;
  seats: number;
  filled: number;
  /** Média de π_x nas rodadas em que a disciplina ainda tinha vaga. `null` se
   * ela nunca esteve no mercado (q_x = 0) — a esgotada não vale o piso da
   * eq. (24), que leria como barata justamente a que todo mundo quis. */
  mean_price: number | null;
  approvals: number;
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
  course: string;
  entry_period: number; // t_a — eq. (31)
  grade_average: number; // N_a — eq. (49)
  approved_hours: number;
  hours_to_graduate: number;
  credits: number;
  enrollments: number;
  approvals: number;
  mean_satisfaction: number;
  graduated_at: number | null;
  /** Período em que foi jubilado. Exclusivo com `graduated_at`: o aluno sai do
   * conjunto ativo por uma porta ou pela outra. */
  dismissed_at: number | null;
}

/** O que aconteceu com uma disciplina que o aluno quis num período.
 * `bids` todo zero = o aluno nem chegou a dar lance (a disciplina saiu de
 * B_a^(t,r): sem vaga, sem carga horária ou sem orçamento). */
export interface RequestRecord {
  discipline: string;
  kind: "required" | "elective" | "free";
  utility: number; // u_{a,x}^(t) — eq. (41)
  bids: number[]; // créditos apostados em cada rodada
  won_round: number | null; // null = recusada
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
  dismissed: boolean;
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
  courses: string[];
  disciplines: string[];
}

export function defaultScenario(): SimulateRequest {
  return {
    disciplines: [],
    courses: [],
    periods: 1,
    entry_periods: null,
    max_residence: 0,
    rounds: 1,
    min_grade: 5,
    base_credits: 10,
    max_hours: 360,
    learning_gain: 2.5,
    credit_return: "none",
    seed: 0,
  };
}
