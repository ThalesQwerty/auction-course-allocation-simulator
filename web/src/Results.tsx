import { useMemo, useState } from "react";
import { MAX_SERIES, MetricChart, SeriesPoint, bandColors, courseColors, formatCount, formatRatio, rampColors, totalColor, usePrefersDark } from "./charts";
import { describeRun, formatRunDate, hasHistories, SimulationRun } from "./history";
import { StudentDetail } from "./StudentDetail";
import { StudentList } from "./StudentList";
import type { CourseSnapshot, RoundReport, SimulateResponse } from "./types";

/** Carregamento sob demanda do detalhe por aluno: ele não cabe no localStorage,
 * então uma execução restaurada de outra sessão precisa ser reexecutada. */
export interface HistoriesLoader {
  loading: boolean;
  error: string | null;
  load: () => void;
}

/** `null` = a grandeza não existe para esse recorte naquele período (não havia
 * aluno). O ponto some do gráfico em vez de virar zero. */
type Accessor = (snapshot: CourseSnapshot) => number | null;

/** Grandezas que não são do aluno, e sim do mercado, e que **não se decompõem**:
 * a escassez e a concorrência são médias de razões por aluno, e o preço é do
 * bem, não de quem o comprou — somar recortes não reconstrói nenhuma das três.
 * Por isso elas não passam pela agregação escolhida: trazem as próprias linhas,
 * numa lista fixa que não vem da população, e que são leituras ordenadas da
 * mesma grandeza (as pontas de uma faixa), nunca recortes de aluno.
 *
 * É o que as separa da ocupação, que divide pela mesma oferta mas é aditiva:
 * ali o parcial é a fatia que o recorte levou, e tem leitura — ver `total`. */
type OverallSeries = { label: string; of: (report: RoundReport) => number | null }[];

/** Nome da linha agregada dos gráficos aditivos. */
const TOTAL_SERIES = "Total";

/** Uma linha por curso, ou uma linha por geração dentro de um curso. Por
 * geração é um curso de cada vez: sobrepor cursos e gerações no mesmo gráfico
 * esconderia justamente a diferença entre eles.
 *
 * O valor "entry" conserva o nome do campo que define a geração
 * (`entry_period`, o t_a da eq. 31): a geração é identificada pelo período em
 * que ingressou. */
type GroupBy = "course" | "entry";

/** Nome da série de um recorte: o curso, ou a geração — o grupo que ingressou
 * naquele período (geração 3 = quem entrou no período 3, esteja ele hoje em
 * que semestre estiver). O aluno nasce numa geração e fica nela até o fim, que
 * é o que mantém cada linha falando sempre do mesmo conjunto de alunos. */
const seriesKey = (snapshot: CourseSnapshot) =>
  snapshot.entry_period === null ? snapshot.course : `Geração ${snapshot.entry_period}`;

/** Como o aluno saiu da simulação: pela conclusão do curso (eq. 40), pelo
 * prazo de jubilamento, ou ainda não saiu. As duas portas são exclusivas. */
const exitLabel = (student: { graduated_at: number | null; dismissed_at: number | null }) =>
  // Testes por veracidade, não contra `null`: numa execução gravada antes do
  // jubilamento existir o campo vem ausente, e `undefined !== null` daria
  // "jubilado no período undefined".
  student.graduated_at
    ? `formado no período ${student.graduated_at}`
    : student.dismissed_at
      ? `jubilado no período ${student.dismissed_at}`
      : "—";

/** Célula de tabela: traço quando a grandeza não existe. */
const cell = (value: number | null, format: (v: number) => string) =>
  value === null ? "—" : format(value);

/** `cohortOf` nulo = uma série por curso; com um curso, uma série por idade
 * dentro dele. Como os dois recortes trazem os mesmos campos, trocar de
 * agregação é trocar a lista que alimenta as séries — nada mais. */
/** Os instantes do eixo: as rodadas de cada período, ou um ponto por período. */
const reportsOf = (result: SimulateResponse, byRound: boolean): RoundReport[] =>
  byRound
    ? result.periods.flatMap((period) => period.rounds)
    : result.periods.map((period) => period.aggregate);

const pointX = (report: RoundReport, byRound: boolean) =>
  byRound ? `${report.period}.${report.round}` : String(report.period);

function buildSeries(
  result: SimulateResponse,
  byRound: boolean,
  accessor: Accessor,
  cohortOf: string | null,
  total: boolean
): SeriesPoint[] {
  return reportsOf(result, byRound).map((report) => {
    const point: SeriesPoint = { x: pointX(report, byRound) };
    const snapshots =
      cohortOf === null
        ? report.by_course
        : report.by_cohort.filter((snapshot) => snapshot.course === cohortOf);
    // A soma sai de **todos** os recortes, não só dos visíveis: esconder um
    // curso tira a linha dele do gráfico, não a parte dele do total.
    let sum: number | null = null;
    for (const snapshot of snapshots) {
      const value = accessor(snapshot);
      if (value === null) continue;
      point[seriesKey(snapshot)] = value;
      sum = (sum ?? 0) + value;
    }
    // O total é a soma dos parciais — e não o agregado da universidade — para
    // acompanhar o recorte: por curso ele dá a universidade inteira, por
    // geração dá o curso escolhido, que é de quem as gerações em tela são
    // parte. Um total que não fosse o total do que está em tela seria uma
    // linha boiando acima de parcelas que não a explicam.
    if (total && sum !== null) point[TOTAL_SERIES] = sum;
    return point;
  });
}

/** Séries das grandezas de mercado: um ponto por instante, lido do agregado do
 * instante. Não passam pelo filtro de cursos nem de gerações — esconder uma
 * série não muda uma grandeza que não é daquele recorte. */
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
const spentOf = (snapshot: CourseSnapshot): number | null =>
  snapshot.credits_per_student === null || snapshot.mean_credits === null
    ? null
    : snapshot.credits_per_student - snapshot.mean_credits;

/** Média da universidade de uma grandeza **por aluno**: as médias dos cursos
 * ponderadas pelos ativos de cada um. Somar não serviria — o valor do curso já
 * traz a população dentro dele, e a soma a contaria duas vezes. */
const perStudentMean = (
  report: RoundReport,
  pick: (snapshot: CourseSnapshot) => number | null
): number | null => {
  let weighted = 0;
  let students = 0;
  for (const snapshot of report.by_course) {
    const value = pick(snapshot);
    if (value === null || snapshot.active === 0) continue;
    weighted += value * snapshot.active;
    students += snapshot.active;
  }
  return students ? weighted / students : null;
};

/** O preço esperado não vem pronto no agregado — a API só o traz por recorte.
 * Mas os cursos particionam os alunos e todos dividem pelas mesmas vagas da
 * universidade, então somar os cursos reconstrói exatamente a oferta total por
 * vaga. */
const overallCreditsPerSeat = (report: RoundReport): number | null => {
  const values = report.by_course
    .map((snapshot) => snapshot.credits_per_seat)
    .filter((value): value is number => value !== null);
  return values.length ? values.reduce((total, value) => total + value, 0) : null;
};

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

/** Ou o gráfico lê o recorte (uma linha por curso ou por geração), ou lê o
 * agregado da universidade (uma linha só) — nunca os dois. */
type ChartSpec = ChartStyle &
  (
    | {
        accessor: Accessor;
        /** Grandeza aditiva no recorte: além dos parciais, o gráfico ganha a
         * linha do total, que é a soma deles. */
        total?: boolean;
      }
    | {
        overall: OverallSeries;
        /** As linhas são leituras ordenadas da mesma grandeza (mín/média/máx,
         * potencial/efetiva) e não medidas diferentes: levam a rampa de faixa
         * no lugar da paleta categórica, e dispensam rótulo na ponta — a ordem
         * vertical já as identifica. */
        band?: boolean;
      }
  );

/** Os gráficos saem em três blocos, cada um respondendo uma pergunta diferente:
 * o leilão alocou bem? (métricas principais), a população anda no curso?
 * (progressão), e o que acontece com o dinheiro? (economia). Dentro de um
 * bloco os eixos são comparáveis entre si. */
const CHART_GROUPS: { title: string; hint: string; charts: ChartSpec[] }[] = [
  {
    title: "Métricas principais",
    hint: "Qualidade da alocação — é por aqui que se compara um mecanismo com outro",
    charts: [
      {
        title: "Eficiência de alocação (ψ̄)",
        hint: "Satisfação média dos alunos ativos — eq. (53)",
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
        hint: "Fatia das vagas ofertadas que foi preenchida — eq. (54). O total é a soma dos parciais: cada curso (ou geração) levou a sua parte das mesmas vagas",
        accessor: (s) => s.metrics?.occupancy ?? null,
        total: true,
        domain: [0, 1],
      },
      {
        // As duas são a mesma conta — alunos por vaga — sobre conjuntos
        // diferentes, então dividem o eixo: é a distância entre elas que se lê,
        // e em gráficos separados essa distância teria de ser estimada no olho.
        title: "Demanda por vaga",
        hint: "Alunos por vaga, na média das disciplinas de cada aluno: a escassez conta quem pode cursar cada uma (demanda potencial) e a concorrência quem de fato a pediu (efetiva) — o vão entre as linhas é a demanda que não virou pedido. Médias de razões por aluno: somar recortes não as reconstrói, então não se dividem por curso nem por geração",
        overall: [
          { label: "Escassez", of: (report) => report.overall.scarcity },
          { label: "Concorrência", of: (report) => report.overall.contention },
        ],
        band: true,
        domain: [0, "auto"],
        format: formatCount,
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
    hint: "Como a população avança no curso ao longo dos períodos",
    charts: [
      {
        title: "Vagas obtidas por aluno",
        hint: "Disciplinas conquistadas por aluno ativo",
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
        hint: "Matriculados no período — |A_k|",
        accessor: (s) => s.active,
        domain: [0, "auto"],
        format: formatCount,
      },
      {
        title: "Formados (fração do recorte)",
        hint: "Concluintes acumulados ÷ alunos que já ingressaram — eq. (40)",
        accessor: (s) => (s.population > 0 ? s.graduated / s.population : null),
        domain: [0, 1],
      },
      {
        title: "Jubilados (fração do recorte)",
        hint:
          "Desligados por decurso de prazo ÷ alunos que já ingressaram. A outra porta de saída: " +
          "quem sai por aqui não aparece nas médias dos períodos seguintes",
        accessor: (s) => (s.population > 0 ? s.dismissed / s.population : null),
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
        // As três na mesma unidade e no mesmo eixo: o que se lê é o vão entre a
        // oferta e o gasto — o crédito que não circulou —, e em gráficos
        // separados ele teria de ser estimado no olho entre duas rampas quase
        // sobrepostas. Medidas diferentes, não as pontas de uma faixa: paleta
        // categórica, não a rampa.
        title: "Créditos por aluno",
        hint: "A contabilidade do período, por aluno ativo: o orçamento no início (C_a^(t,1)), quanto dele foi apostado, quanto virou gasto de fato e o retorno das disciplinas cursadas (Σγ, eq. 34; não inclui Γ_min). O vão orçamento→gasto é o saldo que sobrou; o vão lances→gasto é o que foi comprometido e não pago — lance perdedor, ou o desconto de pagar o preço no lugar do lance. Lances pode passar do orçamento: perder não consome crédito, então o mesmo crédito é apostado de novo na rodada seguinte. As quatro dividem o eixo, então aqui são a média da universidade — por curso e por geração, ver a tabela",
        overall: [
          {
            label: "Orçamento",
            of: (report) => perStudentMean(report, (s) => s.credits_per_student),
          },
          { label: "Lances", of: (report) => perStudentMean(report, (s) => s.mean_bids) },
          { label: "Gasto", of: (report) => perStudentMean(report, spentOf) },
          {
            label: "Retorno",
            of: (report) => perStudentMean(report, (s) => s.mean_credit_return),
          },
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
      {
        // A faixa, e não só a média: uma média estável esconde se o crédito se
        // concentrou em poucas disputas ou se espalhou por todas as vagas.
        title: "Preço de disciplina (π)",
        hint: "Maior lance mal-sucedido de cada disciplina, ou 1 — eq. (24). Só entram as disciplinas que ainda tinham vaga: a esgotada não recebe lance e cairia no piso, o que leria como barata justamente a que todo mundo quis. O preço é do bem, não de quem o comprou, então não se divide por curso nem por geração",
        overall: [
          { label: "Máximo", of: (report) => report.prices?.max ?? null },
          { label: "Médio", of: (report) => report.prices?.mean ?? null },
          { label: "Mínimo", of: (report) => report.prices?.min ?? null },
        ],
        band: true,
        domain: [0, "auto"],
        format: formatCount,
      },
    ],
  },
];

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
  // Geração é o padrão: é o recorte que separa as tendências neste modelo —
  // entre cursos as curvas quase se sobrepõem, entre gerações não.
  const [groupBy, setGroupBy] = useState<GroupBy>("entry");
  // Um filtro por agregação: alternar entre curso e idade não deve descartar o
  // que o usuário já tinha escondido do outro lado.
  const [hiddenCourses, setHiddenCourses] = useState<string[]>([]);
  const [hiddenEntries, setHiddenEntries] = useState<string[]>([]);
  const [pickedCourse, setPickedCourse] = useState<string | null>(null);
  const [allStudents, setAllStudents] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // A cor é atribuída sobre a lista completa de cursos: esconder um curso não
  // repinta os que continuam no gráfico. Vale para toda a tela — a tabela de
  // alunos e a barra lateral seguem a cor do curso em qualquer agregação.
  const colors = useMemo(() => courseColors(result.courses, dark), [result.courses, dark]);
  const hasRounds = result.periods.some((period) => period.rounds.length > 1);
  // Fases do horizonte, lidas da configuração desta execução: os L primeiros
  // períodos recebem geração nova, os demais drenam. Só há L gerações.
  const entrySpan = Math.min(
    run.config.entry_periods ?? run.config.periods,
    run.config.periods
  );
  const drainPeriods = result.periods.length - entrySpan;

  // O curso do recorte por geração só existe enquanto estiver nesta execução:
  // reabrir outra simulação não pode deixar a tela presa num curso que sumiu.
  const entryCourse =
    pickedCourse && result.courses.includes(pickedCourse) ? pickedCourse : result.courses[0] ?? null;
  const byEntry = groupBy === "entry" && entryCourse !== null;

  // As gerações do curso escolhido. O agregado do período basta: uma geração
  // que aparece numa rodada aparece no fim do período também.
  const entries = useMemo(() => {
    if (entryCourse === null) return [];
    const found = new Set<number>();
    for (const period of result.periods) {
      for (const snapshot of period.aggregate.by_cohort) {
        if (snapshot.course === entryCourse && snapshot.entry_period !== null) {
          found.add(snapshot.entry_period);
        }
      }
    }
    return [...found].sort((a, b) => a - b).map((entry) => `Geração ${entry}`);
  }, [result.periods, entryCourse]);

  // Geração é série ordenada: a cor anda pelo círculo cromático conforme o
  // número cresce, em vez de sair da paleta categórica.
  const entryColors = useMemo(() => rampColors(entries, dark), [entries, dark]);
  const seriesColors = byEntry ? entryColors : colors;
  const allSeries = byEntry ? entries : result.courses;
  const hiddenSeries = byEntry ? hiddenEntries : hiddenCourses;
  // Só o recorte por curso trunca: a paleta categórica tem MAX_SERIES cores e
  // não cicla (a cor segue o curso, não a posição na lista), então um nono
  // curso ficaria sem cor própria. A rampa de geração é gerada sob medida para
  // a lista inteira, então mostra todas as gerações da simulação.
  const visible = allSeries.filter((name) => !hiddenSeries.includes(name));
  const series = byEntry ? visible : visible.slice(0, MAX_SERIES);
  const toggleSeries = (name: string) =>
    (byEntry ? setHiddenEntries : setHiddenCourses)((current) =>
      current.includes(name) ? current.filter((other) => other !== name) : [...current, name]
    );

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
          <StudentDetail student={selected} history={selectedHistory} courseColor={colors[selected.course]} />
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
        {(drainPeriods > 0 || run.config.max_residence) && (
          <p className="note">
            {drainPeriods > 0 && (
              <>
                Ingresso nos {entrySpan} primeiros períodos e drenagem nos {drainPeriods}{" "}
                últimos: há <strong>{entrySpan} gerações</strong>, e os períodos de drenagem não
                têm geração correspondente — ninguém entra e a população só diminui. As curvas por
                período caem no fim porque há menos gente disputando, não porque o mecanismo
                melhorou; o recorte por geração não tem essa distorção.{" "}
              </>
            )}
            {run.config.max_residence > 0 && (
              <>
                Jubilamento em {run.config.max_residence} períodos: quem passa do prazo sai da
                disputa. O período em que o aluno é desligado ainda conta nas médias — contar só
                quem fica faria o mecanismo parecer melhor por ter expulsado justamente quem ele
                serviu pior.
              </>
            )}
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
              <option value="course">uma por curso</option>
              <option value="entry">uma por geração</option>
            </select>
          </div>
          {groupBy === "entry" && (
            <div className="field">
              <label>Curso</label>
              <select value={entryCourse ?? ""} onChange={(e) => setPickedCourse(e.target.value)}>
                {result.courses.map((course) => (
                  <option key={course} value={course}>
                    {course}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="field grow">
            <label>{byEntry ? "Gerações no gráfico" : "Cursos no gráfico"}</label>
            <div className="chips">
              {allSeries.map((name) => (
                <button
                  key={name}
                  className={`chip ${hiddenSeries.includes(name) ? "off" : "on"}`}
                  onClick={() => toggleSeries(name)}
                >
                  <span className="swatch" style={{ background: seriesColors[name] }} />
                  {name}
                </button>
              ))}
            </div>
          </div>
        </div>
        {byEntry && (
          <p className="note">
            Uma geração é quem ingressou num mesmo período. Um curso de cada vez: cada aluno
            fica na mesma linha do início ao fim, e a geração só se compara dentro do mesmo
            currículo.
          </p>
        )}
        {!byEntry && allSeries.length > MAX_SERIES && (
          <p className="note">
            Os gráficos mostram no máximo {MAX_SERIES} cursos de cada vez; use os filtros acima.
          </p>
        )}
      </div>

      {CHART_GROUPS.map((group) => (
        <section className="chart-section" key={group.title}>
          <header className="chart-section-head">
            <h2>{group.title}</h2>
            <p>{group.hint}</p>
          </header>
          <div className="chart-grid">
            {group.charts.map((chart) => {
              // Gráfico agregado: traz as próprias linhas, lidas do agregado
              // do instante, sem passar pelo recorte nem pelo filtro de séries.
              // Cada um explica no próprio subtítulo por que não se divide — os
              // motivos são diferentes e nenhuma frase genérica serve aos três.
              return (
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
                          byEntry ? entryCourse : null,
                          chart.total === true
                        )
                  }
                  // O total vem primeiro: é a linha de cima do gráfico, já que
                  // as outras são parte dela.
                  courses={
                    "overall" in chart
                      ? chart.overall.map((line) => line.label)
                      : chart.total
                        ? [TOTAL_SERIES, ...series]
                        : series
                  }
                  colors={
                    "overall" in chart
                      ? (chart.band ? bandColors : courseColors)(
                          chart.overall.map((line) => line.label),
                          dark
                        )
                      : chart.total
                        ? { ...seriesColors, ...totalColor(TOTAL_SERIES, dark) }
                        : seriesColors
                  }
                  domain={chart.domain}
                  format={chart.format ?? formatRatio}
                  zeroLine={chart.zeroLine}
                  band={"overall" in chart && chart.band === true}
                />
              );
            })}
          </div>
        </section>
      ))}

      <div className="panel">
        <h2>Por período (toda a universidade)</h2>
        <table>
          <thead>
            <tr>
              <th>Período</th><th>Ativos</th><th>Concluintes</th><th>Jubilados</th><th>Vagas preenchidas</th>
              <th>Eficiência</th><th>Equidade</th><th>Ocupação</th><th>Escassez</th><th>Concorrência</th><th>Preço esperado</th><th>Semestralização</th>
              <th>CR médio</th><th>Correlação</th>
            </tr>
          </thead>
          <tbody>
            {result.periods.map((period) => {
              const m = period.aggregate.overall;
              return (
                <tr key={period.period}>
                  <td>{period.period}</td>
                  <td>{m.students}</td>
                  <td>{period.graduated_now}</td>
                  <td>{period.dismissed_now ?? 0}</td>
                  <td>{m.allocated}</td>
                  <td>{formatRatio(m.efficiency)}</td>
                  <td>{formatRatio(m.fairness)}</td>
                  <td>{formatRatio(m.occupancy)}</td>
                  <td>{formatCount(m.scarcity)}</td>
                  <td>{formatCount(m.contention)}</td>
                  <td>{cell(overallCreditsPerSeat(period.aggregate), formatCount)}</td>
                  <td>{formatRatio(m.semestralization)}</td>
                  <td>{formatRatio(m.mean_grade_average)}</td>
                  <td>{formatRatio(m.correlation)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>{byEntry ? `Por geração e período — ${entryCourse}` : "Por curso e período"}</h2>
        <p className="note">
          Escassez, concorrência e preço não entram aqui: as duas primeiras são médias de razões
          por aluno e o preço é do bem, não de quem o comprou — somar recortes não reconstrói
          nenhum dos três, e eles só se leem na tabela acima. A ocupação fica, porque é aditiva: o
          parcial é a fatia das vagas que o recorte levou, e os parciais somam o total. O crédito
          também fica — orçamento, lances, gasto, saldo e retorno são por aluno e se recortam —, e é aqui que
          ele se lê por curso e por geração: no gráfico as quatro grandezas dividem o eixo, e por
          isso só cabe ali a média da universidade.
        </p>
        <table>
          <thead>
            <tr>
              <th>{byEntry ? "Geração" : "Curso"}</th><th>Período</th><th>Ativos</th><th>Ingressos</th><th>Concluintes</th><th>Jubilados</th>
              <th>Eficiência</th><th>Equidade</th><th>Ocupação</th><th>Semestralização</th><th>Vagas/aluno</th>
              <th>Orçamento</th><th>Lances</th><th>Gasto</th><th>Saldo</th><th>Retorno</th><th>Horas aprovadas</th>
            </tr>
          </thead>
          <tbody>
            {result.periods.flatMap((period) =>
              (byEntry
                ? period.aggregate.by_cohort.filter((snapshot) => snapshot.course === entryCourse)
                : period.aggregate.by_course
              ).map((snapshot) => (
                <tr key={`${period.period}-${seriesKey(snapshot)}`}>
                  <td>
                    <span
                      className="swatch"
                      style={{ background: seriesColors[seriesKey(snapshot)] }}
                    />{" "}
                    {seriesKey(snapshot)}
                  </td>
                  <td>{period.period}</td>
                  <td>{snapshot.active}</td>
                  <td>{snapshot.population ?? "—"}</td>
                  <td>{snapshot.graduated}</td>
                  <td>{snapshot.dismissed ?? 0}</td>
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
              ))
            )}
          </tbody>
        </table>
      </div>

      {lastPeriod && (
        <div className="panel">
          <h2>Disciplinas no último período simulado</h2>
          <table>
            <thead>
              <tr><th>Disciplina</th><th>Vagas</th><th>Preenchidas</th><th>Preço médio</th><th>Aprovações</th></tr>
            </thead>
            <tbody>
              {lastPeriod.disciplines.map((discipline) => (
                <tr key={discipline.name}>
                  <td>{discipline.name}</td>
                  <td>{discipline.seats}</td>
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
              <th>Aluno</th><th>Curso</th><th>CR</th><th>Horas aprovadas</th>
              <th>Créditos</th><th>Matrículas</th><th>Satisfação média</th><th>Saída</th>
            </tr>
          </thead>
          <tbody>
            {students.map((student) => (
              <tr key={student.id}>
                <td>
                  <button className="link" onClick={() => select(student.id)}>
                    {student.name}
                  </button>
                </td>
                <td>
                  <span className="swatch" style={{ background: colors[student.course] }} /> {student.course}
                </td>
                <td>{formatRatio(student.grade_average)}</td>
                <td>{student.approved_hours} / {student.hours_to_graduate}</td>
                <td>{student.credits}</td>
                <td>{student.enrollments}</td>
                <td>{formatRatio(student.mean_satisfaction)}</td>
                <td>{exitLabel(student)}</td>
              </tr>
            ))}
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
        courses={result.courses}
        colors={colors}
        selectedId={selectedId}
        onSelect={select}
      />
    </div>
  );
}
