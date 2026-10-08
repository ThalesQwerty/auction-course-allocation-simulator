import { useMemo, useState } from "react";
import { MetricChart, SeriesPoint, categoricalColors, formatCount, formatRatio, rampColors, totalColor, usePrefersDark } from "./charts";
import { describeRun, formatRunDate, hasHistories, SimulationRun } from "./history";
import { StudentDetail } from "./StudentDetail";
import { StudentList } from "./StudentList";
import { cohortLabel } from "./types";
import type {
  DisciplineSnapshot,
  GroupSnapshot,
  PeriodReport,
  RoundReport,
  SimulateResponse,
} from "./types";

/** Carregamento sob demanda do detalhe por aluno: ele não cabe no localStorage,
 * então uma execução restaurada de outra sessão precisa ser reexecutada. */
export interface HistoriesLoader {
  loading: boolean;
  error: string | null;
  load: () => void;
}

/** `null` = a grandeza não existe para esse recorte naquele período (não havia
 * aluno). O ponto some do gráfico em vez de virar zero. */
type Accessor = (snapshot: GroupSnapshot) => number | null;

/** Grandezas que não são do aluno, e sim do mercado, e que **não se decompõem**:
 * a escassez e a concorrência são médias de razões por aluno, e o preço é do
 * bem, não de quem o comprou — somar recortes não reconstrói nenhuma das três.
 * Por isso elas não passam pela agregação por geração: trazem as próprias
 * linhas, numa lista fixa que não vem da população, e que são leituras
 * ordenadas da mesma grandeza (as pontas de uma faixa), nunca recortes de aluno.
 *
 * É o que as separa da ocupação, que divide pela mesma oferta mas é aditiva:
 * ali o parcial é a fatia que o recorte levou, e tem leitura — ver `total`. */
type OverallSeries = { label: string; of: (report: RoundReport) => number | null }[];

/** Nome da linha agregada dos gráficos aditivos. */
const TOTAL_SERIES = "Total";

/** Por que recortar a população. Os três eixos particionam os mesmos alunos de
 * formas diferentes, então somar qualquer um deles reproduz a universidade — e
 * trocar de eixo é trocar a lista que alimenta as séries, nada mais.
 *
 * A **geração** é série ordenada (quem entrou antes está mais adiante na
 * grade), e por isso leva a rampa; os **perfis** são categorias sem ordem entre
 * si, e levam a paleta categórica. */
type GroupBy = "cohort" | "aptitude" | "affinity";

interface Axis {
  value: GroupBy;
  label: string;
  /** Rótulo do filtro de séries e do título da tabela. */
  legend: string;
  of: (report: RoundReport) => GroupSnapshot[];
  /** Nome de série a partir da chave crua do recorte. */
  name: (group: string) => string;
  /** Séries ordenadas (geração) ganham rampa; categóricas, a paleta. */
  ordered: boolean;
}

/** Conclusão do curso (eq. 40) — a única porta de saída. Quem não concluiu
 * continua disputando até o fim do horizonte. */
const exitLabel = (student: { graduated_at: number | null }) =>
  student.graduated_at ? `formado no período ${student.graduated_at}` : "em curso";

/** Célula de tabela: traço quando a grandeza não existe. */
const cell = (value: number | null, format: (v: number) => string) =>
  value === null ? "—" : format(value);

/** Os instantes do eixo: as rodadas de cada período, ou um ponto por período. */
const reportsOf = (result: SimulateResponse, byRound: boolean): RoundReport[] =>
  byRound
    ? result.periods.flatMap((period) => period.rounds)
    : result.periods.map((period) => period.aggregate);

const pointX = (report: RoundReport, byRound: boolean) =>
  byRound ? `${report.period}.${report.round}` : String(report.period);

/** Uma linha por grupo do eixo escolhido. O total, quando a grandeza é
 * aditiva, é a soma dos parciais — que é a universidade inteira, porque
 * qualquer um dos eixos particiona a população. */
function buildSeries(
  result: SimulateResponse,
  byRound: boolean,
  accessor: Accessor,
  axis: Axis,
  total: boolean
): SeriesPoint[] {
  return reportsOf(result, byRound).map((report) => {
    const point: SeriesPoint = { x: pointX(report, byRound) };
    // A soma sai de **todos** os grupos, não só dos visíveis: esconder um tira
    // a linha dele do gráfico, não a parte dele do total.
    let sum: number | null = null;
    for (const snapshot of axis.of(report)) {
      const value = accessor(snapshot);
      if (value === null) continue;
      if (snapshot.group !== null) point[axis.name(snapshot.group)] = value;
      sum = (sum ?? 0) + value;
    }
    if (total && sum !== null) point[TOTAL_SERIES] = sum;
    return point;
  });
}

/** Séries das grandezas de mercado: um ponto por instante, lido do agregado do
 * instante. Não passam pelo filtro de gerações — esconder uma série não muda
 * uma grandeza que não é daquele recorte. */
function buildOverallSeries(
  result: SimulateResponse,
  byRound: boolean,
  series: OverallSeries
): SeriesPoint[] {
  return reportsOf(result, byRound).map((report) => {
    const point: SeriesPoint = { x: pointX(report, byRound) };
    for (const { label, of } of series) {
      const value = of(report);
      if (value !== null) point[label] = value;
    }
    return point;
  });
}

/** Gasto do período, por aluno ativo. Não vem da API, mas é exato: a oferta e o
 * saldo são médias sobre os mesmos alunos, então a diferença entre as duas é a
 * média do que cada um consumiu nos leilões. */
const spentOf = (snapshot: GroupSnapshot): number | null =>
  snapshot.credits_per_student === null || snapshot.mean_credits === null
    ? null
    : snapshot.credits_per_student - snapshot.mean_credits;

interface ChartStyle {
  title: string;
  hint: string;
  domain?: [number | "auto", number | "auto"];
  format?: (value: number) => string;
  zeroLine?: boolean;
  /** Grandeza que só existe ao fim do período (as notas saem depois das
   * rodadas). Esses gráficos ignoram o eixo por rodada — ali a série seria
   * inteira nula — e continuam em período, com o aviso no subtítulo. */
  periodOnly?: boolean;
}

/** Ou o gráfico lê o recorte (uma linha por grupo do eixo escolhido), ou lê o
 * agregado da universidade (uma linha só) — nunca os dois. */
type ChartSpec = ChartStyle &
  (
    | {
        accessor: Accessor;
        /** Grandeza aditiva no recorte: além dos parciais, o gráfico ganha a
         * linha do total, que é a soma deles. */
        total?: boolean;
      }
    | { overall: OverallSeries }
  );

/** Os gráficos saem em três blocos, cada um respondendo uma pergunta diferente:
 * o leilão alocou bem? (métricas principais), a população anda na grade?
 * (progressão), e o que acontece com o dinheiro? (economia). Dentro de um
 * bloco os eixos são comparáveis entre si. */
const CHART_GROUPS: { title: string; hint: string; charts: ChartSpec[] }[] = [
  {
    title: "Métricas principais",
    hint: "Qualidade da alocação — é por aqui que se compara um mecanismo com outro",
    charts: [
      {
        title: "Eficiência de alocação (ψ̄)",
        hint: "Satisfação média dos alunos que disputaram — eq. (53). A utilidade é zero fora do conjunto elegível, então ψ é a fração do que o aluno podia cursar e conseguiu: 1 é atingível. Quem acaba de ingressar não entra na conta — recebe vaga garantida em tudo que lhe é elegível e pontuaria 1 sem ter disputado nada",
        accessor: (s) => s.metrics?.efficiency ?? null,
        domain: [0, 1],
      },
      {
        title: "Equidade (índice de Jain, φ)",
        hint: "1 = todos igualmente satisfeitos — eq. (55)",
        accessor: (s) => s.metrics?.fairness ?? null,
        domain: [0, 1],
      },
      {
        title: "Correlação CR × satisfação (λ)",
        hint: "Positivo = quem tem CR maior se sai melhor — eq. (57)",
        accessor: (s) => s.metrics?.correlation ?? null,
        domain: [-1, 1],
        zeroLine: true,
      },
      {
        // Aditiva: todos dividem pelas mesmas vagas da universidade, então a
        // ocupação de um recorte é a fatia que ele levou e os parciais somam o
        // total. É o que a separa das outras métricas da oferta.
        title: "Taxa de ocupação (θ)",
        hint: "Fatia das vagas ofertadas que foi preenchida — eq. (54). O total é a soma dos parciais: cada recorte levou a sua parte das mesmas vagas",
        accessor: (s) => s.metrics?.occupancy ?? null,
        total: true,
        domain: [0, 1],
      },
      {
        title: "Semestralização (σ̄)",
        hint: "Carga aprovada ÷ máximo possível desde o ingresso; 1 = ninguém atrasado",
        accessor: (s) => s.metrics?.semestralization ?? null,
        domain: [0, 1],
      },
    ],
  },
  {
    title: "Progressão",
    hint: "Como a população avança na grade ao longo dos períodos",
    charts: [
      {
        title: "Vagas obtidas por aluno",
        hint: "Disciplinas conquistadas por aluno ativo, contando a matrícula garantida de quem ingressa",
        accessor: (s) => s.metrics?.allocations_per_student ?? null,
        domain: [0, "auto"],
        format: formatCount,
      },
      {
        title: "CR médio (N̄)",
        hint: "Coeficiente de rendimento no início do período — eq. (56)",
        accessor: (s) => s.metrics?.mean_grade_average ?? null,
        domain: [0, 10],
      },
      {
        title: "Alunos ativos",
        hint: "Matriculados no período — |A^(t)|",
        accessor: (s) => s.active,
        domain: [0, "auto"],
        format: formatCount,
      },
      {
        title: "Formados (fração do recorte)",
        hint: "Concluintes acumulados ÷ alunos que já ingressaram. Concluir é aprovar em todas as disciplinas da grade — eq. (40)",
        accessor: (s) => (s.population > 0 ? s.graduated / s.population : null),
        domain: [0, 1],
      },
      {
        title: "Carga horária aprovada (média)",
        hint: "Progressão curricular média dos alunos ativos",
        accessor: (s) => s.mean_approved_hours,
        domain: [0, "auto"],
        format: formatCount,
      },
    ],
  },
  {
    title: "Economia de créditos",
    hint: "De onde vem o crédito, quanto dele circula e o que ele compra",
    charts: [
      {
        // As quatro na mesma unidade e no mesmo eixo: o que se lê é o vão entre
        // a oferta e o gasto — o crédito que não circulou —, e em gráficos
        // separados ele teria de ser estimado no olho entre duas rampas quase
        // sobrepostas. Medidas diferentes, não as pontas de uma faixa: paleta
        // categórica, não a rampa.
        title: "Créditos por aluno",
        hint: "A contabilidade do período, por aluno ativo: o orçamento no início (C_a^(t,1)), quanto dele foi apostado, quanto virou gasto de fato e o retorno das disciplinas cursadas (Σγ, eq. 34; não inclui Γ_min). O vão orçamento→gasto é o saldo que sobrou; o vão lances→gasto é o que foi comprometido e não pago — lance perdedor, ou o desconto de pagar o preço no lugar do lance. Lances pode passar do orçamento: perder não consome crédito, então o mesmo crédito é apostado de novo na rodada seguinte. A matrícula garantida entra como lance e gasto pelo mesmo valor, que é o que o sistema lança na conta do ingressante. As quatro dividem o eixo, então aqui são a média da universidade — por recorte, ver a tabela",
        overall: [
          { label: "Orçamento", of: (report) => report.overall.credits_per_student },
          { label: "Lances", of: (report) => report.overall.mean_bids },
          { label: "Gasto", of: (report) => spentOf(report.overall) },
          { label: "Retorno", of: (report) => report.overall.mean_credit_return },
        ],
        domain: [0, "auto"],
        format: formatCount,
        periodOnly: true,
      },
      {
        // A leitura normalizada do mesmo fato, e a única comparável entre
        // cenários: o nível em créditos depende de Γ_min, a fração não.
        title: "Fração do orçamento gasta",
        hint: "Quanto do crédito em mãos o aluno conseguiu gastar. Cai quando o crédito entra mais rápido do que a oferta de vagas deixa gastar — o estoque incha e a moeda perde poder, que é o que o preço do leilão reflete",
        accessor: (s) =>
          s.credits_per_student !== null && s.credits_per_student > 0 && s.mean_credits !== null
            ? (s.credits_per_student - s.mean_credits) / s.credits_per_student
            : null,
        domain: [0, 1],
      },
    ],
  },
];

/** ---------------------------------------------------------------------------
 * Gráficos por disciplina
 *
 * O outro lado do mercado. Os gráficos por aluno perguntam quem foi bem
 * servido; estes perguntam **o que** foi disputado — e a resposta só aparece
 * quando as disciplinas se agrupam por alguma propriedade que elas
 * compartilham. Disciplinas com o mesmo valor caem no mesmo grupo, e os três
 * eixos são o período na grade (que vem dos pré-requisitos), o número de vagas
 * e a carga horária.
 *
 * Tudo aqui é por período, nunca por rodada: a disciplina só fecha preço,
 * ocupação e aprovações ao fim do período.
 * ------------------------------------------------------------------------- */
type DisciplineGroupBy = "period" | "seats" | "hours";

interface DisciplineAxis {
  value: DisciplineGroupBy;
  label: string;
  legend: string;
  key: (discipline: DisciplineSnapshot) => number;
  name: (key: number) => string;
}

const DISCIPLINE_AXES: DisciplineAxis[] = [
  {
    value: "period",
    label: "uma por período da grade",
    legend: "Períodos da grade no gráfico",
    key: (d) => d.curriculum_period,
    name: (key) => `${key}º período`,
  },
  {
    value: "seats",
    label: "uma por número de vagas",
    legend: "Tamanhos de turma no gráfico",
    key: (d) => d.seats,
    name: (key) => `${key} vagas`,
  },
  {
    value: "hours",
    label: "uma por carga horária",
    legend: "Cargas horárias no gráfico",
    key: (d) => d.hours,
    name: (key) => `${key} h`,
  },
];

/** O agregado de um grupo de disciplinas num período. Guarda as razões por
 * disciplina (`contentions`, `prices`) além das somas, porque as duas coisas se
 * leem de formas diferentes: concorrência e preço são **do bem**, e o grupo é a
 * média delas; ocupação e aprovação são razões de contagens, e o grupo é a
 * razão das somas. Fazer média de ocupações daria peso igual a uma disciplina
 * de 40 vagas e a uma de 120. */
interface DisciplineGroup {
  seats: number;
  filled: number;
  approvals: number;
  /** requests ÷ seats de cada disciplina do grupo. */
  contentions: number[];
  /** π das disciplinas que chegaram a estar no mercado; as esgotadas não entram. */
  prices: number[];
}

const mean = (values: number[]): number | null =>
  values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;

function groupDisciplines(
  period: PeriodReport,
  axis: DisciplineAxis
): Map<number, DisciplineGroup> {
  const groups = new Map<number, DisciplineGroup>();
  for (const discipline of period.disciplines) {
    const key = axis.key(discipline);
    const group =
      groups.get(key) ??
      { seats: 0, filled: 0, approvals: 0, contentions: [], prices: [] };
    group.seats += discipline.seats;
    group.filled += discipline.filled;
    group.approvals += discipline.approvals;
    // Disciplina sem vaga não tem concorrência — a razão seria divisão por zero.
    if (discipline.seats > 0) group.contentions.push(discipline.requests / discipline.seats);
    if (discipline.mean_price !== null) group.prices.push(discipline.mean_price);
    groups.set(key, group);
  }
  return groups;
}

interface DisciplineChart extends ChartStyle {
  of: (group: DisciplineGroup) => number | null;
}

const DISCIPLINE_CHARTS: { title: string; hint: string; charts: DisciplineChart[] }[] = [
  {
    title: "Oferta e disputa",
    hint: "O que cada tipo de disciplina viveu no período — é aqui que a gradação de escassez embutida na grade aparece",
    charts: [
      {
        title: "Concorrência por vaga",
        hint: "Candidatos por vaga de cada disciplina (quantos a pediram ÷ vagas), na média do grupo. A matrícula garantida conta como pedido: o ingressante não disputou, mas ocupa a vaga, e para quem recursa a pressão é a mesma",
        of: (g) => mean(g.contentions),
        domain: [0, "auto"],
        format: formatCount,
      },
      {
        title: "Preço de disciplina (π)",
        hint: "Maior lance mal-sucedido de cada disciplina, ou 1 — eq. (24) —, na média do grupo. Só entram as que ainda tinham vaga: a esgotada não recebe lance e cairia no piso, o que leria como barata justamente a que todo mundo quis",
        of: (g) => mean(g.prices),
        domain: [0, "auto"],
        format: formatCount,
      },
      {
        title: "Taxa de ocupação",
        hint: "Vagas preenchidas ÷ vagas ofertadas do grupo. É a razão das somas, não a média das razões: senão uma disciplina de 40 vagas pesaria o mesmo que uma de 120. Diferente da ocupação por aluno, esta não é fatia de nada — é o quanto cada tipo de oferta encheu",
        of: (g) => (g.seats > 0 ? g.filled / g.seats : null),
        domain: [0, 1],
      },
      {
        title: "Taxa de aprovação",
        hint: "Aprovados ÷ matriculados do grupo ao fim do período. Mede a dificuldade do que foi cursado, não a alocação — serve para ver se um tipo de disciplina represa a fila por reprovação em vez de por falta de vaga",
        of: (g) => (g.filled > 0 ? g.approvals / g.filled : null),
        domain: [0, 1],
      },
    ],
  },
];

function buildDisciplineSeries(
  result: SimulateResponse,
  axis: DisciplineAxis,
  of: (group: DisciplineGroup) => number | null
): SeriesPoint[] {
  return result.periods.map((period) => {
    const point: SeriesPoint = { x: String(period.period) };
    for (const [key, group] of groupDisciplines(period, axis)) {
      const value = of(group);
      if (value !== null) point[axis.name(key)] = value;
    }
    return point;
  });
}

export function Results({
  run,
  onReuseConfig,
  histories,
}: {
  run: SimulationRun;
  onReuseConfig: () => void;
  histories: HistoriesLoader;
}) {
  const result = run.result;
  const dark = usePrefersDark();
  const [byRound, setByRound] = useState(false);
  const [groupBy, setGroupBy] = useState<GroupBy>("cohort");
  const [disciplineGroupBy, setDisciplineGroupBy] = useState<DisciplineGroupBy>("seats");
  const [hiddenDisciplines, setHiddenDisciplines] = useState<Record<DisciplineGroupBy, string[]>>(
    { period: [], seats: [], hours: [] }
  );
  // Um filtro por eixo: trocar de recorte não deve descartar o que o usuário
  // já tinha escondido do outro.
  const [hidden, setHidden] = useState<Record<GroupBy, string[]>>({
    cohort: [],
    aptitude: [],
    affinity: [],
  });
  const [allStudents, setAllStudents] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const hasRounds = result.periods.some((period) => period.rounds.length > 1);
  // Fases do horizonte, lidas da configuração desta execução: os L primeiros
  // períodos recebem geração nova, os demais drenam. Só há L gerações.
  const entrySpan = Math.min(
    run.config.entry_periods ?? run.config.periods,
    run.config.periods
  );
  const drainPeriods = result.periods.length - entrySpan;

  // As gerações da execução. O agregado do último período basta: toda geração
  // que já ingressou continua na lista até o fim.
  const cohorts = useMemo(() => {
    const found = new Set<number>();
    for (const period of result.periods) {
      for (const snapshot of period.aggregate.by_cohort) {
        if (snapshot.group !== null) found.add(Number(snapshot.group));
      }
    }
    return [...found].sort((a, b) => a - b);
  }, [result.periods]);

  const axes: Axis[] = useMemo(
    () => [
      {
        value: "cohort",
        label: "uma por geração",
        legend: "Gerações no gráfico",
        of: (report) => report.by_cohort,
        name: (group) => cohortLabel(Number(group)),
        ordered: true,
      },
      {
        value: "aptitude",
        label: "uma por perfil de aptidão",
        legend: "Perfis de aptidão no gráfico",
        of: (report) => report.by_aptitude,
        name: (group) => group,
        ordered: false,
      },
      {
        value: "affinity",
        label: "uma por perfil de afinidade",
        legend: "Perfis de afinidade no gráfico",
        of: (report) => report.by_affinity,
        name: (group) => group,
        ordered: false,
      },
    ],
    []
  );
  const axis = axes.find((a) => a.value === groupBy) ?? axes[0];

  const allSeries = useMemo(() => {
    if (axis.value === "cohort") return cohorts.map(cohortLabel);
    // Execuções gravadas antes dos perfis existirem não trazem as listas: o
    // último relatório ainda diz quais grupos o eixo tem.
    const profiles =
      axis.value === "aptitude" ? result.aptitude_profiles : result.affinity_profiles;
    return profiles ?? [];
  }, [axis, cohorts, result.aptitude_profiles, result.affinity_profiles]);

  // Geração é série ordenada: a cor anda pelo círculo cromático conforme o
  // número cresce. Perfil é categoria sem ordem, e sai da paleta categórica.
  // Nos dois casos a cor é atribuída sobre a lista inteira — esconder um grupo
  // não repinta os que ficam.
  const colors = useMemo(
    () => (axis.ordered ? rampColors : categoricalColors)(allSeries, dark),
    [axis.ordered, allSeries, dark]
  );
  const hiddenSeries = hidden[axis.value];
  const series = allSeries.filter((name) => !hiddenSeries.includes(name));
  const toggleSeries = (name: string) =>
    setHidden((current) => ({
      ...current,
      [axis.value]: current[axis.value].includes(name)
        ? current[axis.value].filter((other) => other !== name)
        : [...current[axis.value], name],
    }));

  // A cor do aluno segue sempre a geração, em qualquer agregação: a barra
  // lateral e a tabela de alunos não mudam de paleta quando o gráfico muda de
  // eixo, senão a mesma pessoa trocaria de cor a cada clique.
  const cohortColors = useMemo(
    () => rampColors(cohorts.map(cohortLabel), dark),
    [cohorts, dark]
  );

  // Os grupos de disciplina do eixo escolhido, em ordem crescente da grandeza:
  // período 1..6, 40/80/120 vagas, 60/90 h. Todos são séries **ordenadas**,
  // então levam a rampa de cor, como as gerações.
  const disciplineAxis =
    DISCIPLINE_AXES.find((a) => a.value === disciplineGroupBy) ?? DISCIPLINE_AXES[0];
  const disciplineSeries = useMemo(() => {
    const found = new Set<number>();
    for (const period of result.periods) {
      for (const discipline of period.disciplines) found.add(disciplineAxis.key(discipline));
    }
    return [...found].sort((a, b) => a - b).map(disciplineAxis.name);
  }, [result.periods, disciplineAxis]);
  const disciplineColors = useMemo(
    () => rampColors(disciplineSeries, dark),
    [disciplineSeries, dark]
  );
  const hiddenDisciplineSeries = hiddenDisciplines[disciplineGroupBy];
  const visibleDisciplineSeries = disciplineSeries.filter(
    (name) => !hiddenDisciplineSeries.includes(name)
  );
  const toggleDisciplineSeries = (name: string) =>
    setHiddenDisciplines((current) => ({
      ...current,
      [disciplineGroupBy]: current[disciplineGroupBy].includes(name)
        ? current[disciplineGroupBy].filter((other) => other !== name)
        : [...current[disciplineGroupBy], name],
    }));

  const students = allStudents ? result.students : result.students.slice(0, 50);
  const lastPeriod = result.periods[result.periods.length - 1];

  const selected = result.students.find((student) => student.id === selectedId) ?? null;
  const selectedHistory = result.histories.find((h) => h.student_id === selectedId) ?? null;

  function select(id: string | null) {
    setSelectedId(id);
    if (id && !hasHistories(run)) histories.load();
  }

  return (
    <div className="rail-layout">
      <div className="rail-layout-main">
      <div className="page-head">
        <div>
          <h1>Simulação de {formatRunDate(run.at)}</h1>
          <p className="note">{describeRun(run)}</p>
        </div>
        <button className="secondary" onClick={onReuseConfig}>
          Reabrir esta configuração
        </button>
      </div>

      {histories.error && <div className="error-banner">{histories.error}</div>}

      {selected ? (
        histories.loading ? (
          <div className="panel">
            <p className="empty-state">
              Reexecutando a simulação para reconstruir o histórico de {selected.name}…
            </p>
          </div>
        ) : selectedHistory ? (
          <StudentDetail
            student={selected}
            history={selectedHistory}
            cohortColor={cohortColors[cohortLabel(selected.entry_period)]}
          />
        ) : (
          <div className="panel">
            <p className="empty-state">
              O detalhe por aluno desta execução não está carregado.{" "}
              <button className="link" onClick={histories.load}>
                Reexecutar a simulação
              </button>{" "}
              para reconstruí-lo — a seed garante o mesmo resultado.
            </p>
          </div>
        )
      ) : (
        <>
      <div className="panel">
        <h2>Resultado — {result.periods.length} períodos simulados</h2>
        <p className="note">
          Três recortes da mesma população: a <strong>geração</strong> (quem ingressou num mesmo
          período) e os dois <strong>perfis</strong> do aluno — a aptidão, que dá a distribuição
          das notas, e a afinidade, que diz o quanto ele concentra a preferência. Somar qualquer um
          deles reproduz a universidade; o que muda de um para o outro é a pergunta. Em todos, o
          aluno fica na mesma linha do início ao fim.
        </p>
        <p className="note">
          <strong>Quem acabou de ingressar conta como gente, não como dado.</strong> O ingressante
          recebe vaga garantida nas disciplinas de 1º período — exatamente as elegíveis para ele —,
          então pontuaria ψ = 1 contra CR = 0 sem ter disputado nada. Ele entra em{" "}
          <em>alunos ativos</em>, <em>ingressos</em> e <em>formados</em>, que são contagens de
          pessoas, e fica fora de toda média por aluno. Por isso a série de uma geração só começa
          no período <em>seguinte</em> ao seu ingresso, e o 1º período da simulação não tem métrica
          nenhuma — ali todo mundo é calouro.
        </p>
        {drainPeriods > 0 && (
          <p className="note">
            Ingresso nos {entrySpan} primeiros períodos e drenagem nos {drainPeriods} últimos: há{" "}
            <strong>{entrySpan} gerações</strong>, e os períodos de drenagem não têm geração
            correspondente — ninguém entra e a população só diminui. As curvas por período caem no
            fim porque há menos gente disputando, não porque o mecanismo melhorou; o recorte por
            geração não tem essa distorção.
          </p>
        )}
        <div className="field-row">
          <div className="field">
            <label>Eixo horizontal</label>
            <select value={byRound ? "round" : "period"} onChange={(e) => setByRound(e.target.value === "round")} disabled={!hasRounds}>
              <option value="period">por período</option>
              <option value="round">por rodada (período.rodada)</option>
            </select>
          </div>
          <div className="field">
            <label>Linhas do gráfico</label>
            <select value={groupBy} onChange={(e) => setGroupBy(e.target.value as GroupBy)}>
              {axes.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field grow">
            <label>{axis.legend}</label>
            <div className="chips">
              {allSeries.map((name) => (
                <button
                  key={name}
                  className={`chip ${hiddenSeries.includes(name) ? "off" : "on"}`}
                  onClick={() => toggleSeries(name)}
                >
                  <span className="swatch" style={{ background: colors[name] }} />
                  {name}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <h2 className="chart-part-head">Gráficos por aluno</h2>

      {CHART_GROUPS.map((group) => (
        <section className="chart-section" key={group.title}>
          <header className="chart-section-head">
            <h2>{group.title}</h2>
            <p>{group.hint}</p>
          </header>
          <div className="chart-grid">
            {group.charts.map((chart) => (
              // Gráfico agregado: traz as próprias linhas, lidas do agregado do
              // instante, sem passar pelo recorte nem pelo filtro de séries.
              // Cada um explica no próprio subtítulo por que não se divide — os
              // motivos são diferentes e nenhuma frase genérica serve aos três.
              <MetricChart
                key={chart.title}
                title={chart.title}
                hint={
                  byRound && chart.periodOnly
                    ? `${chart.hint} · só existe ao fim do período, então este gráfico segue em período`
                    : chart.hint
                }
                data={
                  "overall" in chart
                    ? buildOverallSeries(result, byRound && !chart.periodOnly, chart.overall)
                    : buildSeries(
                        result,
                        byRound && !chart.periodOnly,
                        chart.accessor,
                        axis,
                        chart.total === true
                      )
                }
                // O total vem primeiro: é a linha de cima do gráfico, já que
                // as outras são parte dela.
                series={
                  "overall" in chart
                    ? chart.overall.map((line) => line.label)
                    : chart.total
                      ? [TOTAL_SERIES, ...series]
                      : series
                }
                colors={
                  "overall" in chart
                    ? categoricalColors(chart.overall.map((line) => line.label), dark)
                    : chart.total
                      ? { ...colors, ...totalColor(TOTAL_SERIES, dark) }
                      : colors
                }
                domain={chart.domain}
                format={chart.format ?? formatRatio}
                zeroLine={chart.zeroLine}
              />
            ))}
          </div>
        </section>
      ))}

      <h2 className="chart-part-head">Gráficos por disciplina</h2>

      <div className="panel">
        <p className="note">
          Aqui o recorte é da <strong>oferta</strong>, não da população: as disciplinas se agrupam
          por uma propriedade que compartilham, e disciplinas com o mesmo valor caem no mesmo
          grupo. Sempre por período — a disciplina só fecha preço, ocupação e aprovações ao fim
          dele.
        </p>
        <div className="field-row">
          <div className="field">
            <label>Linhas do gráfico</label>
            <select
              value={disciplineGroupBy}
              onChange={(e) => setDisciplineGroupBy(e.target.value as DisciplineGroupBy)}
            >
              {DISCIPLINE_AXES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field grow">
            <label>{disciplineAxis.legend}</label>
            <div className="chips">
              {disciplineSeries.map((name) => (
                <button
                  key={name}
                  className={`chip ${hiddenDisciplineSeries.includes(name) ? "off" : "on"}`}
                  onClick={() => toggleDisciplineSeries(name)}
                >
                  <span className="swatch" style={{ background: disciplineColors[name] }} />
                  {name}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {DISCIPLINE_CHARTS.map((group) => (
        <section className="chart-section" key={group.title}>
          <header className="chart-section-head">
            <h2>{group.title}</h2>
            <p>{group.hint}</p>
          </header>
          <div className="chart-grid">
            {group.charts.map((chart) => (
              <MetricChart
                key={chart.title}
                title={chart.title}
                hint={chart.hint}
                data={buildDisciplineSeries(result, disciplineAxis, chart.of)}
                series={visibleDisciplineSeries}
                colors={disciplineColors}
                domain={chart.domain}
                format={chart.format ?? formatRatio}
              />
            ))}
          </div>
        </section>
      ))}

      <div className="panel">
        <h2>Por período (toda a universidade)</h2>
        <table>
          <thead>
            <tr>
              <th>Período</th><th>Ativos</th><th>Concluintes</th><th>Vagas preenchidas</th>
              <th>Eficiência</th><th>Equidade</th><th>Ocupação</th><th>Escassez</th><th>Concorrência</th><th>Preço esperado</th><th>Semestralização</th>
              <th>CR médio</th><th>Correlação</th>
            </tr>
          </thead>
          <tbody>
            {result.periods.map((period) => {
              const snapshot = period.aggregate.overall;
              const m = snapshot.metrics;
              return (
                <tr key={period.period}>
                  <td>{period.period}</td>
                  <td>{snapshot.active}</td>
                  <td>{period.graduated_now}</td>
                  <td>{m?.allocated ?? "—"}</td>
                  <td>{cell(m?.efficiency ?? null, formatRatio)}</td>
                  <td>{cell(m?.fairness ?? null, formatRatio)}</td>
                  <td>{cell(m?.occupancy ?? null, formatRatio)}</td>
                  <td>{cell(m?.scarcity ?? null, formatCount)}</td>
                  <td>{cell(m?.contention ?? null, formatCount)}</td>
                  <td>{cell(snapshot.credits_per_seat, formatCount)}</td>
                  <td>{cell(m?.semestralization ?? null, formatRatio)}</td>
                  <td>{cell(m?.mean_grade_average ?? null, formatRatio)}</td>
                  <td>{cell(m?.correlation ?? null, formatRatio)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Por {axis.legend.split(" no gráfico")[0].toLowerCase()} e período</h2>
        <p className="note">
          Escassez, concorrência e preço não entram aqui: as duas primeiras são médias de razões
          por aluno e o preço é do bem, não de quem o comprou — somar recortes não reconstrói
          nenhum dos três, e eles só se leem na tabela acima. A ocupação fica, porque é aditiva: o
          parcial é a fatia das vagas que o recorte levou, e os parciais somam o total. O crédito
          também fica — orçamento, lances, gasto, saldo e retorno são por aluno e se recortam —, e
          é aqui que ele se lê por recorte: no gráfico as quatro grandezas dividem o eixo, e por
          isso só cabe ali a média da universidade.
        </p>
        <table>
          <thead>
            <tr>
              <th>Recorte</th><th>Período</th><th>Ativos</th><th>Ingressos</th><th>Concluintes</th>
              <th>Eficiência</th><th>Equidade</th><th>Ocupação</th><th>Semestralização</th><th>Vagas/aluno</th>
              <th>Orçamento</th><th>Lances</th><th>Gasto</th><th>Saldo</th><th>Retorno</th><th>Horas aprovadas</th>
            </tr>
          </thead>
          <tbody>
            {result.periods.flatMap((period) =>
              axis.of(period.aggregate).map((snapshot) => {
                const label = axis.name(snapshot.group ?? "");
                return (
                  <tr key={`${period.period}-${label}`}>
                    <td>
                      <span className="swatch" style={{ background: colors[label] }} /> {label}
                    </td>
                    <td>{period.period}</td>
                    <td>{snapshot.active}</td>
                    <td>{snapshot.population}</td>
                    <td>{snapshot.graduated}</td>
                    <td>{cell(snapshot.metrics?.efficiency ?? null, formatRatio)}</td>
                    <td>{cell(snapshot.metrics?.fairness ?? null, formatRatio)}</td>
                    <td>{cell(snapshot.metrics?.occupancy ?? null, formatRatio)}</td>
                    <td>{cell(snapshot.metrics?.semestralization ?? null, formatRatio)}</td>
                    <td>{cell(snapshot.metrics?.allocations_per_student ?? null, formatCount)}</td>
                    <td>{cell(snapshot.credits_per_student, formatCount)}</td>
                    <td>{cell(snapshot.mean_bids, formatCount)}</td>
                    <td>{cell(spentOf(snapshot), formatCount)}</td>
                    <td>{cell(snapshot.mean_credits, formatCount)}</td>
                    <td>{cell(snapshot.mean_credit_return, formatCount)}</td>
                    <td>{cell(snapshot.mean_approved_hours, formatCount)}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {lastPeriod && (
        <div className="panel">
          <h2>Disciplinas no último período simulado</h2>
          <p className="note">
            "Garantidas" são as vagas entregues aos ingressantes antes de o leilão abrir: só as
            disciplinas de 1º período têm, e é o que explica uma delas chegar à primeira rodada
            já quase cheia. Sem vaga sobrando, a disciplina sai do mercado e não forma preço.
          </p>
          <table>
            <thead>
              <tr>
                <th>Disciplina</th><th>Período</th><th>Carga</th><th>Vagas</th>
                <th>Garantidas</th><th>Pedidos</th><th>Preenchidas</th>
                <th>Preço médio</th><th>Aprovações</th>
              </tr>
            </thead>
            <tbody>
              {lastPeriod.disciplines.map((discipline) => (
                <tr key={discipline.name}>
                  <td>{discipline.name}</td>
                  <td className="muted-cell">{discipline.curriculum_period}º</td>
                  <td className="muted-cell">{discipline.hours} h</td>
                  <td>{discipline.seats}</td>
                  <td>{discipline.granted || "—"}</td>
                  <td>{discipline.requests}</td>
                  <td>{discipline.filled}</td>
                  <td>{cell(discipline.mean_price, formatCount)}</td>
                  <td>{discipline.approvals}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="panel">
        <h2>Alunos — {result.students.length} no total</h2>
        <table>
          <thead>
            <tr>
              <th>Aluno</th><th>Geração</th><th>Aptidão</th><th>Afinidade</th><th>CR</th>
              <th>Horas aprovadas</th><th>Créditos</th><th>Matrículas</th>
              <th>Satisfação média</th><th>Saída</th>
            </tr>
          </thead>
          <tbody>
            {students.map((student) => {
              const label = cohortLabel(student.entry_period);
              return (
                <tr key={student.id}>
                  <td>
                    <button className="link" onClick={() => select(student.id)}>
                      {student.name}
                    </button>
                  </td>
                  <td>
                    <span className="swatch" style={{ background: cohortColors[label] }} /> {label}
                  </td>
                  <td className="muted-cell">{student.aptitude}</td>
                  <td className="muted-cell">{student.affinity}</td>
                  <td>{formatRatio(student.grade_average)}</td>
                  <td>{student.approved_hours} / {student.hours_to_graduate}</td>
                  <td>{student.credits}</td>
                  <td>{student.enrollments}</td>
                  <td>{formatRatio(student.mean_satisfaction)}</td>
                  <td>{exitLabel(student)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {result.students.length > 50 && (
          <div className="actions">
            <button className="secondary" onClick={() => setAllStudents((current) => !current)}>
              {allStudents ? "mostrar apenas os 50 primeiros" : `mostrar todos os ${result.students.length}`}
            </button>
          </div>
        )}
      </div>
        </>
      )}
      </div>

      <StudentList
        students={result.students}
        cohorts={cohorts}
        aptitudes={result.aptitude_profiles ?? []}
        affinities={result.affinity_profiles ?? []}
        colors={cohortColors}
        selectedId={selectedId}
        onSelect={select}
      />
    </div>
  );
}
