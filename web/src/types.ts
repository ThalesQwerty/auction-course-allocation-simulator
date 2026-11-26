
export interface DisciplineInput {
  name: string;
   /** Turmas ofertadas */
  classes: number;
  hours: number; // w_x — carga horária
  unlocks: string[];
   /** Matrícula garantida de quem ingressa */
  entry: boolean;
   /** Optativa: não desbloqueia nada, não é de entrada, e concluir não exige aprovar em cada uma — exige somar `elective_hours` entre as aprovadas */
  elective?: boolean;
  /** Flutuação própria do gosto por esta disciplina; ausente cai na do cenário */
  fluctuation?: number;
}

/** Nome de uma coorte: o grupo que ingressou naquele período (coorte 3 = quem entrou no período 3, esteja ele hoje em que semestre estiver) */
export const cohortLabel = (entryPeriod: number): string =>
  `Coorte ${entryPeriod}`;

/** A distribuição de **disponibilidade** da população, uma só */
export interface AvailabilityShape {
  /** σ das horas; a média sai dele e da chance de alcançar W_a */
  hours_sd: number;
  full_load_rate: number; // em (0, 1)
}

export interface Scenario {
  disciplines: DisciplineInput[];
   /** Alunos por turma */
  class_size: number;
   /** P_apr — a probabilidade de a nota alcançar `min_grade` */
  approval_rate: number;
   /** σ — o desvio padrão das notas */
  grade_sd: number;
   /** ω — o ganho por repetição */
  repetition_gain: number;
  availability: AvailabilityShape;
  /** Desvio do abalo que o quantil da disponibilidade sofre a cada período */
  availability_fluctuation: number;
  selectivity_mean: number;
  selectivity_sigma: number;
  selectivity_fluctuation: number;
  /** A log-normal do interesse por **horário**, a segunda metade do produto que forma o interesse por turma */
  schedule_mean: number;
  schedule_sigma: number;
  schedule_fluctuation: number;
   /** Os pontos de corte das faixas, um eixo por grandeza */
  grade_cuts: number[];
  reserve_cuts: number[];
  slots: number;
  /** A log-normal do interesse por **disciplina** */
  interest_mean: number;
  interest_sigma: number; // > 0
  interest_fluctuation: number;
  max_hours: number;
   /** R — períodos para concluir */
  max_residence: number;
   /** A seed da primeira simulação da comparação; as seguintes contam de 1 em 1 a partir dela */
  first_seed: number;
   /** Quantos ingressantes entram em **cada turma de disciplina de entrada**, no máximo `class_size` */
  students_per_entry_class: number;
  rounds: number; // |R|
  min_grade: number; // n_apr
   /** X — carga horária optativa exigida para concluir, somada entre as optativas aprovadas */
  elective_hours: number;
  min_credits: number; // C_min — orçamento mínimo do período
  max_credits: number | null; // C_max — orçamento máximo do período
  seed: number;
}

/** Os dois mecanismos de alocação comparados pelo trabalho */
export type Mechanism = "credits" | "ranking";

/** Os modelos comparados, na ordem do caminho — que é também a ordem do eixo, da legenda e das cores */
interface ArmDescription {
  key: string;
  label: string;
   /** Qual miolo de rodada este braço usa — o que decide se há lance e saldo a mostrar */
  mechanism: Mechanism;
   /** Rótulo curto: em espaço apertado cabe pouco, e o nome inteiro fica na legenda */
  short: string;
   /** `strokeDasharray` do traçado — a dimensão que separa os modelos em todo gráfico, já que a cor pertence ao recorte */
  dash: string;
  hint: string;
}

/** Os **dois modelos comparados**, na ordem do eixo */
export const COMPARISON_ARMS: ArmDescription[] = [
  {
    key: "ranking_greedy",
    label: "Ordenação por CR",
    mechanism: "ranking",
    short: "CR",
    dash: "1 3",
    hint: "a linha de base: matrícula por histórico. Os alunos entram em ordem decrescente de CR e cada um leva o que quer, na própria ordem de preferência, enquanto houver vaga e carga — eqs. (49)-(50). Ordinal: a alocação usa só a ordem, nunca a magnitude. Excluir não custa nada aqui — não há moeda a perder",
  },
  {
    key: "credits_return",
    label: "Leilão com PLI",
    mechanism: "credits",
    short: "Leilão",
    dash: "",
    hint: "o modelo proposto (Seção 7.1): o aluno reparte um orçamento de créditos em lances por disciplina, um PLI resolve a alocação e o segundo preço cobra. O saldo atravessa o período (eq. 36) e o f_γ da eq. (34) o alimenta — round(nota/10 · k · preço) do que pagou, de modo que a vaga só rende mais do que custou com nota bem acima da de corte. É a única fonte de mérito do leilão, e quem exclui não recupera nada",
  },
];

/** Os degraus do caminho, que **não** rodam por padrão */
export const ABLATION_ARMS: ArmDescription[] = [
  {
    key: "credits_greedy",
    label: "Bidding points",
    mechanism: "credits",
    short: "Bidding points",
    dash: "1 3",
    hint: "o mecanismo de pontos das business schools (Sönmez & Ünver 2010): lances repartidos de um orçamento, atendidos em ordem decrescente. Ordinal como o CR — o que muda é só a mensagem, que passa a ser um número por disciplina em vez de um por aluno",
  },
  {
    key: "credits_ilp",
    label: "Leilão igualitário",
    mechanism: "credits",
    short: "Igualitário",
    dash: "7 4",
    hint: "o mesmo leilão, com o orçamento fixo: todo aluno abre todo período com C_min, nada atravessa o período e o f_γ da eq. (34) fica desligado (k = 0). Separa o que a moeda compra do que o acúmulo compra. Saiu do padrão em 19/11/2026, quando o trabalho passou a comparar dois modelos",
  },
];

export const armLabel = (key: string): string =>
  [...COMPARISON_ARMS, ...ABLATION_ARMS].find((arm) => arm.key === key)?.label ?? key;

export const armShort = (key: string): string =>
  [...COMPARISON_ARMS, ...ABLATION_ARMS].find((arm) => arm.key === key)?.short ?? key;

/** Uma comparação: o mesmo cenário rodado em cada modelo, N vezes */
export interface CompareRequest extends Omit<Scenario, "seed"> {
  runs: number; // N
   /** Quais braços rodar, pelas chaves de `COMPARISON_ARMS` */
  arms: string[];
}

export const MAX_COMPARISON_RUNS = 100;

/** As métricas de período de uma simulação, sem reduzir — o que o recorte por período desenha */
export interface PeriodSeries {
  period: number[];
  students: number[];
  satisfaction: number[];
   /** θ — a carga cursada sobre a obtida; `null` onde ninguém do recorte obteve vaga, porque sem denominador não há razão */
  attendance: (number | null)[];
  mean_round: (number | null)[];
   /** Progresso e fração de concluintes: a resposta montada do banco os traz; a gravada em JSON, não */
  progress?: number[];
  graduation_rate?: number[];
  fairness: number[];
   /** N̄ — o CR médio do recorte */
  grade_average?: number[];
   /** A economia de créditos, só do leilão: oferta de abertura, consumo da eq */
  credits_supply?: (number | null)[];
  credits_spent?: (number | null)[];
  credits_returned?: (number | null)[];
  exclusion_rate: number[];
   /** Os seis estados e a saturação: só nas execuções gravadas em JSON */
  request_states?: RequestStates[];
  allocations_per_round?: (number | null)[][];
}

/** Uma simulação reduzida a um ponto por métrica — o que vira um valor dentro das tabelas */
export interface RunSummary {
  seed: number;
   /** Períodos efetivamente publicados; menor que |T| se a população se esvaziou antes do horizonte */
  periods: number;
  /** Quantos desses períodos usaram todas as |R| rodadas — a censura de r̄ */
  capped_periods?: number;
   /** Concluintes da simulação */
  graduates: number;
  dismissed: number;
  population: number;
  satisfaction: number; // ψ̄ — eq. (53)
   /** Ocupação (θ): carga horária obtida ÷ W_a */
  attendance: number | null;
  mean_round: number | null;
   /** Progresso: carga aprovada ÷ carga que conclui o curso, na média ponderada dos períodos */
  progress: number;
  fairness: number; // φ — eq. (55)
   /** N̄ — o CR médio */
  grade_average: number;
   /** Desperdício: a fração das vagas obtidas que foi largada antes de virar aula */
  exclusion_rate: number;
   /** Δψ — a **dissipação**: a satisfação que foi alocada e não chegou a ser consumida, porque o aluno descartou o que não cabia na carga efetiva */
   /** Os seis estados em média por aluno, reduzidos a um ponto cada */
  request_states: RequestStates;
   /** Períodos do ingresso ao diploma, na média dos concluintes; conta o período da formatura */
  time_to_graduate: number | null;
   /** Vagas obtidas por aluno **em cada rodada**, na ordem delas: o índice r-1 é a rodada r, e há |R| posições */
  allocations_per_round: (number | null)[];
   /** A série por período desta simulação */
  by_period?: PeriodSeries;
   /** As linhas cruas desta simulação, em colunas paralelas */
  observations?: Observations;
}

/** As linhas cruas de uma simulação: uma posição por (aluno medido, período medido).

    É daqui que a interface recorta as faixas. `grade_average` e `reserve` dão o
    rótulo da faixa; `won` é o peso de `mean_round`, porque r̄ do recorte é a média
    das rodadas **por vaga concedida**. */
export interface Observations {
  period: number[];
  grade_average: number[];
  reserve: number[];
  satisfaction: number[];
  attendance: (number | null)[];
  progress: number[];
  mean_round: (number | null)[];
  won: number[];
}

/** Um dos modelos comparados e as suas N simulações */
export interface ArmResult {
  key: string;
  mechanism: Mechanism;
  runs: RunSummary[];
  /** Um ponto por aluno medido, de todas as seeds juntas */
  points?: StudentPoint[];
  /** O agregado da coorte por período, reduzido entre as seeds. Só o recorte "Geral": as faixas a interface recorta de `RunSummary.observations` */
  series?: AxisBands[];
}

/** Os recortes **espaciais** da tela de comparação — as cores das linhas */
export type CutAxis =
  | "overall"
  | "grade_average"
  | "reserve"
   /** Só existe no leilão: no `ranking` o braço não produz o eixo, e a série dele não vem na resposta */
  | "credits";

export type Band = [number, number, number];

/** Um grupo de um recorte, reduzido entre as seeds ponto a ponto da régua */
export interface GroupBands {
  group: string;
   /** O ponto da régua: período, idade ou coorte, conforme o `ruler` do eixo */
  x?: number[];
  period?: number[];
  n: number[];
  values: Record<string, (Band | null)[]>;
}

/** Um ponto da dispersão: um aluno medido, de ponta a ponta do curso */
export interface StudentPoint {
  grade_average: number;
  reserve: number;
  satisfaction: number;
  attendance: number | null;
  progress: number;
  mean_round: number | null;
  graduated: boolean;
}

/** Os grupos de um recorte espacial */
export interface AxisBands {
  axis: CutAxis;
  groups: GroupBands[];
}

/** As visualizações, prontas para desenhar: a API já fez a transformação.

    `series` é a série por período recortada em faixas, com mediana e interquartil
    **entre as seeds**; `curve` é a métrica sobre uma grandeza de vida inteira em
    faixas de quantil, com o interquartil **entre alunos**; `boxes` é o eixo X
    colapsado numa caixa por (braço, métrica) sobre as seeds. A tela não calcula
    nada disso. */
export interface SeriesPayload {
  axis: CutAxis;
   /** Os nomes das faixas, na ordem da legenda */
  groups: string[];
  arms: Record<string, GroupBands[]>;
}

export interface CurvePoint {
  x: number;
  q1: number;
  median: number;
  q3: number;
  n: number;
}

export interface CurvePayload {
  axis: "grade_average" | "reserve";
  bins: number;
   /** braço → métrica → os pontos da curva */
  arms: Record<string, Record<string, CurvePoint[]>>;
}

export interface BoxStats {
   /** Em quantas seeds este braço ficou acima da linha de base, par a par */
  paired?: { up: number; comparable: number } | null;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  n: number;
}

export interface SeedRow {
  arm: string;
  seed: number;
  periods: number;
  graduates: number;
  [metric: string]: number | string | null;
}

export interface BoxesPayload {
  baseline: string;
   /** Uma linha por (braço, seed), para a tabela do rodapé */
  seeds: SeedRow[];
   /** braço → métrica → a caixa */
  arms: Record<string, Record<string, BoxStats>>;
}

/** Uma comparação em banco, como `/comparacoes` a devolve. O `cenario` vem como JSON em texto, do jeito que está gravado */
export interface ComparisonHead {
  nome: string;
  bytes: number;
  rotulo: string | null;
  criada_em: string;
  iniciada_em: string | null;
  terminada_em: string | null;
  duracao_ms: number | null;
  estado: "pendente" | "rodando" | "pausada" | "concluida" | "falhou";
  cenario: string;
  seeds: number;
  bracos: string[];
  coorte_medida: number | null;
  rodadas_teto: number;
   /** Passos já dados e o teto deles. O teto é nulo nas comparações criadas antes da conta existir */
  etapas: number;
  etapas_total: number | null;
  erro: string | null;
  pendentes: number;
  rodando: number;
  concluidas: number;
  falhas: number;
}

/** O cabeçalho com o estado de cada simulação: o que a tela consulta para acompanhar */
export interface ComparisonState extends ComparisonHead {
  simulacoes: {
    id: number;
    braco: string;
    seed: number;
    estado: "pendente" | "rodando" | "concluida" | "falhou";
    tentativas: number;
    iniciada_em: string | null;
    terminada_em: string | null;
    duracao_ms: number | null;
    periodos: number | null;
    etapas: number;
    erro: string | null;
    periodos_gravados: number;
  }[];
}

/** Uma execução gravada em `resultados/`, como a lista da API a devolve */
export interface SavedResult {
  name: string;
  kind: string;
  at: string;
  bytes: number;
  config: CompareRequest;
}

/** Uma execução gravada, inteira */
export interface StoredRun {
  kind: string;
  at: string;
  config: CompareRequest;
  result: CompareResponse;
}

export interface CompareResponse {
  saved_to: string | null;
   /** O nome com que a execução ficou gravada, que endereça `/results/{nome}` */
  saved_as?: string | null;
  runs: number;
  arms: ArmResult[];
   /** As duas distribuições de entrada do cenário */
  interest_distribution?: number[];
  grade_distribution?: number[];
}

/** Os seis estados de uma solicitação, em **média por aluno** */
export interface RequestStates {
  not_eligible: number;
  not_requested: number;
   /** Pediu e não foi atendido */
  refused: number;
  excluded: number;
  failed: number;
  approved: number;
}

export interface Metrics {
  students: number;
  allocated: number;
  allocations_per_student: number;
   /** ψ̄ — eq */
  satisfaction: number;
   /** Ocupação (θ) — carga horária obtida no período ÷ W_a, média dos alunos medidos */
   /** θ — carga cursada ÷ carga obtida, média de quem obteve alguma vaga */
  attendance: number | null;
  attendance_students: number | null;
   /** Progresso — carga aprovada do histórico ÷ carga mínima para concluir (as obrigatórias inteiras mais a exigência optativa) */
  progress: number;
   /** Fidelidade da mensagem — o cosseno entre o vetor de lances normalizado e o de utilidades, sobre o elegível */
  fairness: number; // φ — Jain, eq. (55)
   /** Vagas que o recorte obteve e largou */
  excluded: number | null;
   /** Desperdício: as vagas excluídas sobre as obtidas */
  exclusion_rate: number | null;
   /** Aproveitamento **efetivo**: carga retida ÷ W_a */
   /** Os seis estados de solicitação, em média por aluno — a seção "Solicitações de disciplinas" */
  request_states: RequestStates | null;
   /** Escassez: elegíveis por vaga */
  scarcity: number;
   /** Concorrência: solicitantes por vaga */
  contention: number;
  mean_grade_average: number; // N̄ — eq. (56)
   /** Carga horária aprovada ÷ (W_a × idade em períodos), média do recorte */
  semestralization: number;
}

/** Um recorte de alunos num instante: a universidade inteira (`overall`) ou uma coorte (`by_cohort`) */
export interface GroupSnapshot {
   /** Quem é este recorte: `null` na universidade inteira e o período de ingresso (t_a, eq */
  group: string | null;
   /** Nulos quando o recorte não tem aluno no período: não havia ninguém, o que é diferente de ninguém ter ficado satisfeito */
  metrics: Metrics | null;
  active: number;
   /** Alunos do recorte que já ingressaram, tenham concluído ou não */
  population: number;
  graduated: number;
   /** Jubilados acumulados */
  dismissed: number;
  mean_credits: number | null;
  mean_approved_hours: number | null;
   /** Oferta de créditos do início do período (C_a^(t,1), antes dos lances), dividida pelos alunos do recorte e pelas vagas de toda a universidade — a segunda é o preço que uma vaga teria se todo o crédito fosse gasto */
  credits_per_student: number | null;
  credits_per_seat: number | null;
   /** Créditos apostados no período por aluno ativo, somando as rodadas */
  mean_bids: number | null;
   /** Retorno de créditos do período por aluno ativo (Σγ, eq */
  mean_credit_return: number | null;
}

/** Dispersão do preço de mercado (π_x, eq */
export interface PriceStats {
  min: number;
  mean: number;
  max: number;
}

export interface RoundReport {
  period: number;
  round: number; // 0 = agregado do período
  overall: GroupSnapshot;
   /** O mesmo instante agregado por coorte */
  by_cohort: GroupSnapshot[];
   /** `null` quando nenhuma disciplina estava no mercado: sem oferta não há preço, e 0 ali se leria como "de graça" */
  prices: PriceStats | null;
}

export interface DisciplineSnapshot {
   /** O nome da **turma**: é dela que são a vaga, o preço e a demanda */
  name: string;
  discipline: string;
   /** Os três eixos pelos quais as disciplinas se agrupam nos gráficos */
  curriculum_period: number;
  hours: number;
  difficulty: number;
  classes: number;
   /** O **turno** da turma — `day` ou `night` */
  shift: string;
   /** O horário da turma, como `"Diurno 3"` */
  schedule: string;
  seats: number;
  filled: number;
   /** Vagas entregues à matrícula garantida, antes da primeira rodada */
  granted: number;
   /** Quantos alunos pediram a disciplina no período — deram lance em alguma rodada, ou a receberam na matrícula garantida */
  requests: number;
   /** Média de π_x nas rodadas em que a disciplina ainda tinha vaga */
  mean_price: number | null;
  approvals: number;
   /** Vagas desta disciplina obtidas e depois largadas */
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
  /** As âncoras dele, como quantis em (0, 1) */
  availability_anchor: number;
  selectivity_anchor: number;
  grade_average: number; // N_a — eq. (49)
  approved_hours: number;
   /** S — a carga da grade inteira */
  hours_to_graduate: number;
  credits: number;
  enrollments: number;
  approvals: number;
  mean_satisfaction: number;
   /** Período em que concluiu o curso — a **única** porta de saída */
  graduated_at: number | null;
  dismissed_at: number | null;
}

/** Rodada de `won_round` quando a vaga não veio de rodada nenhuma: é a matrícula garantida do ingressante, concedida antes de o leilão abrir */
export const GUARANTEED_ROUND = 0;

/** O que aconteceu com uma disciplina que o aluno quis num período */
export interface RequestRecord {
  discipline: string;
  utility: number; // ũ_{a,x}^(t) — a utilidade, não o interesse
  bids: number[]; // créditos apostados em cada rodada
   /** Rodada em que obteve a vaga; `null` = indeferida */
  won_round: number | null;
  paid: number; // eq. (27)
   /** Obteve a vaga e não cursou: a disponibilidade do período não comportou */
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
  credits_returned: number; // Σγ do período — eq. (35)
  credits_end: number;
  satisfaction: number; // psi_a^(t) — eq. (51)
  grade_average: number; // CR no início do período — eq. (49)
  approved_hours: number;
  enrolled_hours: number;
   /** Carga que ele de fato cursou e o teto que a disponibilidade lhe deu: `retained_hours <= effective_load`, e o vão para `enrolled_hours` é o que ele largou */
  retained_hours: number;
  effective_load: number;
  requests: RequestRecord[];
  graduated: boolean;
}

export interface StudentHistory {
  student_id: string;
  periods: StudentPeriodRecord[];
}

/** O pedido do traço de **uma** simulação da comparação: o cenário dela mais o par `(braço, seed)` que endereça a simulação */
export interface TraceRequest extends Omit<Scenario, "seed"> {
  arm: string;
  seed: number;
}

/** O contexto de mercado de um período: a oferta disciplina a disciplina */
export interface TracePeriod {
  period: number;
  disciplines: DisciplineSnapshot[];
}

/** Uma simulação inteira, aluno a aluno — a tela de depuração do projeto */
export interface TraceResponse {
  arm: string;
  seed: number;
  periods: TracePeriod[];
  students: StudentSummary[];
   /** Detalhe período a período de cada aluno, com uma linha por disciplina elegível — inclusive as que ele nem chegou a pedir */
  histories: StudentHistory[];
   /** As **turmas** ofertadas, na ordem da grade: são elas que a tela endereça, porque é delas que são o lance e a vaga */
  disciplines: string[];
   /** Turma → disciplina */
  classes: Record<string, string>;
  curriculum_periods: Record<string, number>;
}

export interface PlaygroundRequest {
  mechanism: Mechanism;
  rounds: number;
  seed: number;
  min_grade: number;
  approval_rate: number;
  grade_sd: number;
  classes: { name: string; discipline: string; seats: number; hours: number }[];
  students: {
    id: string;
    credits: number;
    cr: number;
    max_hours: number;
    utilities: Record<string, number>;
    eligible: string[];
    availability?: number;
    selectivity: number;
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
  load: number | null;
  retained: string[];
  excluded: string[];
}

export interface PlaygroundResponse {
  rounds: PlaygroundRound[];
  closing: PlaygroundClosing[];
  grades: { student_id: string; name: string; grade: number }[];
}

/** |T| — o horizonte da janela estacionária */
export const horizonFor = (maxResidence: number): number =>
  2 * maxResidence - 1;
