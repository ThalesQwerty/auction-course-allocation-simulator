import { useMemo, useState } from "react";
import {
  AllocationTimeChart,
  Histogram,
  LineSample,
  SeriesChart,
  categoricalColors,
  formatCount,
  formatRatio,
  inkFor,
  soloColor,
  usePrefersDark,
} from "./charts";
import type {
  AllocationTimeLine,
  SeriesArmStyle,
  SeriesGroupStyle,
  SeriesLine,
} from "./charts";
import {
  AMPLITUDE,
  CUTS,
  RULERS,
  amplitudeGroups,
  amplitudeLines,
  cutGroups,
  pointsOf,
  rulerOf,
  seriesOf,
} from "./bands";
import type { CutChoice } from "./bands";
import { boxStats } from "./equations";
import { describeComparison, formatRunDate, ComparisonRun } from "./history";
import { Trace } from "./Trace";
import { COMPARISON_ARMS } from "./types";
import type { ClassCut, Ruler, RunSummary } from "./types";

/** Períodos com uma casa: o tempo de formatura anda em frações de período, e
 * duas casas sugeririam uma precisão que a amostra não tem. */
const formatPeriods = (value: number) =>
  value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Uma grandeza comparada entre os modelos. `of` é o ponto de uma simulação,
 * que as tabelas usam; `band` é a chave da série por período em
 * `GroupBands.values`, que os gráficos desenham. Sem `band` a métrica fica só
 * nas tabelas — é o caso do tempo de formatura, que é da simulação inteira. */
interface Metric {
  id: string;
  title: string;
  /** Rótulo curto, para a coluna "Métrica" das tabelas. */
  short: string;
  of: (run: RunSummary) => number | null;
  band?: string;
  /** Limites naturais da grandeza; o domínio é folgado em torno dos dados mas
   * nunca passa daqui. Ausente quando a grandeza não tem teto. */
  bounds?: [number, number];
  /** De que lado está o melhor resultado — é o que decide o sinal de "seeds a
   * favor". `null` quando a métrica **descreve** em vez de pontuar: λ e a
   * saturação são o caso. */
  betterWhen: "higher" | "lower" | null;
  format: (value: number) => string;
  zeroLine?: boolean;
}

/** A economia de créditos — **exclusiva do leilão**. Fora dele estas grandezas
 * saem `null`, e não zeradas: não há moeda, e zero se leria como "ninguém
 * gastou". A linha do CR, portanto, nem aparece nestes gráficos.
 *
 * Nenhuma delas pontua. Gastar mais não é melhor nem pior — é o que o
 * mecanismo faz com o orçamento —, e por isso elas ficam fora das tabelas de
 * comparação, que existem para dizer qual lado ganhou. */
const CREDIT_METRICS: Metric[] = [
  {
    id: "credits_supply",
    title: "Orçamento de créditos por aluno",
    short: "Orçamento",
    of: () => null,
    band: "credits_supply",
    // C_a^(t,1), a oferta de abertura: o que o aluno tinha para apostar antes
    // de qualquer lance. Com C_max ela tem teto, mas o teto é do cenário e não
    // da grandeza, então a régua se ajusta aos dados.
    bounds: [0, Infinity],
    betterWhen: null,
    format: formatCount,
  },
  {
    id: "credits_spent",
    title: "Créditos gastos por aluno",
    short: "Gastos",
    of: () => null,
    band: "credits_spent",
    bounds: [0, Infinity],
    betterWhen: null,
    format: formatCount,
  },
  {
    id: "credits_returned",
    title: "Créditos retornados por aluno",
    short: "Retornados",
    of: () => null,
    band: "credits_returned",
    bounds: [0, Infinity],
    betterWhen: null,
    format: formatCount,
  },
];

/** Os recortes do gráfico de preço. Eles repartem a **oferta**, e não os
 * alunos: é o único gráfico da tela cujas linhas não são grupos de gente. */
const CLASS_CUTS: { axis: ClassCut; label: string }[] = [
  { axis: "classes", label: "Turmas" },
  { axis: "hours", label: "Carga horária" },
  { axis: "difficulty", label: "Dificuldade" },
  { axis: "shift", label: "Turno" },
  { axis: "curriculum_period", label: "Período" },
];

/** O rótulo em português de um grupo da oferta. A API manda o **valor** como
 * chave ("2", "60", "1.4"), sem idioma, e é aqui que ele vira texto. */
const classGroupLabel = (axis: ClassCut, key: string): string => {
  if (key === "elective") return "optativa";
  const value = Number(key);
  const number = Number.isFinite(value) ? value.toLocaleString("pt-BR") : key;
  switch (axis) {
    case "classes":
      return value === 1 ? "1 turma" : `${number} turmas`;
    case "hours":
      return `${number} h`;
    case "difficulty":
      return `dificuldade ${number}`;
    case "shift":
      return key === "night" ? "noturna" : "diurna";
    case "curriculum_period":
      return `${number}º período`;
  }
};

/** As métricas de alocação — as que avaliam a qualidade do que foi alocado.
 *
 * Nada de crédito: orçamento, preço e retorno não existem do lado da linha de
 * base, e comparar um mecanismo com o vazio não compara nada.
 *
 * Duas saíram em 08/10. A **ocupação** (θ), porque com o calouro fora do
 * recorte ela deixou de se ler como "o quanto a universidade encheu" — as vagas
 * garantidas continuam ocupadas e não entram mais no numerador; quem quer essa
 * leitura a tem nos gráficos por disciplina de uma simulação. E a
 * **semestralização**, que deu lugar ao tempo de formatura: mede a mesma coisa
 * — progressão na grade — num número que se lê direto. */
const METRICS: Metric[] = [
  {
    id: "efficiency",
    title: "Satisfação (ψ̄)",
    short: "Satisfação (ψ̄)",
    of: (run) => run.efficiency,
    band: "efficiency",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "utilization",
    title: "Ocupação (θ)",
    short: "Ocupação (θ)",
    of: (run) => run.utilization,
    band: "utilization",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "progress",
    title: "Progresso",
    short: "Progresso",
    of: (run) => run.progress,
    band: "progress",
    bounds: [0, 1],
    // Pontua, mas com a mesma ressalva do tempo de formatura: quem fecha a
    // grade sai da medida, de modo que um mecanismo que forma mais gente pode
    // exibir progresso *menor* entre os que ficaram. Lê-se com a fração de
    // concluintes ao lado.
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "fidelity",
    title: "Fidelidade da mensagem",
    short: "Fidelidade",
    of: (run) => run.fidelity,
    band: "fidelity",
    bounds: [0, 1],
    // Descreve, não pontua: dizer qual lado é melhor exigiria escolher entre
    // expressar intensidade e ser simples de usar, e isso é juízo de quem lê.
    betterWhen: null,
    format: formatRatio,
  },
  {
    id: "fairness",
    title: "Equidade (índice de Jain, φ)",
    short: "Equidade (φ)",
    of: (run) => run.fairness,
    band: "fairness",
    bounds: [0, 1],
    betterWhen: "higher",
    format: formatRatio,
  },
  {
    id: "exclusion_rate",
    title: "Desperdício de vaga",
    short: "Desperdício",
    of: (run) => run.exclusion_rate,
    band: "exclusion_rate",
    bounds: [0, 1],
    // A vaga que ninguém cursou é perda pura: saiu da oferta e não virou aula.
    betterWhen: "lower",
    format: formatRatio,
  },
  {
    id: "correlation",
    title: "Correlação CR × satisfação (λ)",
    short: "Correlação (λ)",
    of: (run) => run.correlation,
    band: "correlation",
    bounds: [-1, 1],
    betterWhen: null,
    format: formatRatio,
    zeroLine: true,
  },
  {
    id: "grade_average",
    title: "CR médio (N̄)",
    short: "CR médio",
    of: (run) => run.grade_average,
    band: "grade_average",
    // A régua inteira, como manda `paddedScale`: o CR tem contradomínio, e
    // fechá-la em torno da amostra faria um vão de 0,05 ocupar meio cartão.
    bounds: [0, 10],
    // Descreve, não pontua. Ele sobe tanto quando o aluno vai melhor quanto
    // quando o mecanismo o roteia para turma mais fácil, e separar as duas
    // exige a dificuldade, que está nos gráficos por disciplina.
    betterWhen: null,
    format: formatRatio,
  },
  {
    id: "graduation_rate",
    title: "Fração de concluintes",
    short: "Concluintes",
    of: (run) => (run.population ? run.graduates / run.population : null),
    // Fração, e não contagem: o absoluto depende do tamanho do ingresso, e os
    // braços só são comparáveis na mesma escala.
    //
    // **Não há gráfico de jubilados ao lado.** Como o horizonte é derivado do
    // ciclo de vida, ao fim dele todo mundo saiu por uma das duas portas, e a
    // fração de jubilados é exatamente `1 − esta`. Seria a mesma curva
    // espelhada, ocupando espaço e convidando a ler duas vezes o mesmo fato.
    //
    // Por período ela é **acumulada**: quem concluiu até ali sobre quem já
    // tinha entrado. No último período é o número da tabela.
    band: "graduation_rate",
    betterWhen: "higher",
    bounds: [0, 1],
    format: formatRatio,
  },
  {
    id: "time_to_graduate",
    title: "Tempo de formatura (períodos)",
    short: "Tempo (períodos)",
    of: (run) => run.time_to_graduate,
    // Sem série: o tempo é da simulação inteira, e a versão por período
    // ("quanto levou quem concluiu em t") seria outra grandeza, com viés de
    // sobrevivência. Fica nas tabelas.
    betterWhen: "lower",
    format: formatPeriods,
  },
];


/** As quatro frações do funil de uma solicitação — `equations.request_funnel`.
 *
 * Cada uma divide pelo **nó anterior**, não pelo catálogo: é o que faz cada
 * painel se mexer só quando o nó dele se mexe, e é o que permite as quatro
 * dividirem a mesma régua de 0 a 1. Elas substituíram os seis painéis de
 * contagem, que subiam e desciam juntos porque dividiam o mesmo denominador.
 *
 * As contagens continuam na resposta da API (os seis estados), e é a elas que
 * se recorre quando uma fração sai vazia — um nó sem ninguém não tem fração. */
const FUNNEL = [
  { key: "requested_share", title: "Fração de solicitadas" },
  { key: "granted_share", title: "Fração de deferidas" },
  { key: "attended_share", title: "Fração de cursadas" },
  { key: "approved_share", title: "Fração de aprovadas" },
] as const;

const ORDINALS = ["1ª", "2ª", "3ª", "4ª", "5ª", "6ª", "7ª", "8ª", "9ª", "10ª"];

/** Uma métrica por rodada do cenário: as vagas obtidas por aluno naquela
 * rodada. Quantas são depende do |R| da simulação, então elas são construídas a
 * partir do resultado, e não de uma lista fixa. */
const roundMetrics = (rounds: number): Metric[] =>
  Array.from({ length: rounds }, (_, index) => {
    const ordinal = ORDINALS[index] ?? `${index + 1}ª`;
    return {
      id: `round-${index}`,
      title: `Alocações por aluno (${ordinal} rodada)`,
      short: `Alocações (${ordinal} rodada)`,
      of: (run) => run.allocations_per_round?.[index] ?? null,
      band: `round_${index + 1}`,
      bounds: [0, Infinity],
      betterWhen: null,
      format: formatCount,
    };
  });

/** Os dois braços do leilão que isolam o acúmulo: eles diferem em **uma**
 * coisa só — `credits_ilp` abre todo período em C_min e não tem retorno,
 * `credits_return` carrega o saldo e o alimenta com o k do cenário. Comparar
 * qualquer outro par mediria o acúmulo somado a outra diferença. */
const WITH_ACCUMULATION = "credits_return";
const WITHOUT_ACCUMULATION = "credits_ilp";

/** A linha de base, contra a qual as diferenças da tabela de resumo são
 * medidas: a matrícula por CR com varredura, que é o mecanismo real das
 * universidades brasileiras. */
const BASELINE = "ranking_greedy";

/** O que a amplitude muda em todo gráfico da tela.
 *
 * A régua passa a se ajustar aos dados: o vão entre perfis é pequeno perto do
 * contradomínio da grandeza, e desenhá-lo em [0, 1] o colaria no eixo. Ele
 * também não tem sinal — é uma distância —, então a marca do zero sai mesmo
 * onde a grandeza a pedia. */
const AMPLITUDE_CHART = {
  bounds: [0, Infinity] as [number, number],
  zeroLine: false,
  foot: "vão entre os grupos do eixo",
};

/** Sinal explícito: numa coluna de diferenças, "+0,04" e "−0,04" se distinguem
 * de relance e "0,04" não. */
const formatDelta = (value: number, format: (v: number) => string) =>
  `${value > 0 ? "+" : value < 0 ? "−" : ""}${format(Math.abs(value))}`;

export function Comparison({
  run,
  onReuseConfig,
}: {
  run: ComparisonRun;
  onReuseConfig: () => void;
}) {
  const dark = usePrefersDark();
  const result = run.result;
  const ink = inkFor(dark);
  /** As duas escolhas que governam todos os gráficos: a **régua** do eixo X
   * (período, idade ou coorte) e o **recorte** das linhas (a universidade
   * inteira ou um dos quatro eixos de perfil). O modelo é a terceira
   * dimensão e não é escolha — ele é sempre o traçado.
   *
   * Uma só de cada para a tela inteira: o que elas trocam são os eixos de
   * todos os gráficos, e lê-los com recortes diferentes lado a lado é o que
   * não se quer. */
  const [rulerChoice, setRuler] = useState<Ruler>("period");
  const [cutChoice, setCut] = useState<CutChoice>("overall");
  /** O recorte da oferta no gráfico de preço. Ele é independente do recorte
   * das demais linhas: um reparte turmas, o outro reparte alunos. */
  const [priceCutChoice, setPriceCut] = useState<ClassCut>("curriculum_period");

  /** Os dois leilões são escolha de quem configura a comparação. Sem os dois
   * não há o que isolar, e a tabela do acúmulo sairia inteira em traços. */
  const hasBothAuctions = [WITH_ACCUMULATION, WITHOUT_ACCUMULATION].every((key) =>
    result.arms.some((arm) => arm.key === key)
  );

  /** Os modelos que rodaram, com o traçado de cada um. */
  const arms: SeriesArmStyle[] = useMemo(
    () =>
      COMPARISON_ARMS.filter((arm) => result.arms.some((a) => a.key === arm.key)).map(
        (arm) => ({ key: arm.key, label: arm.label, dash: arm.dash })
      ),
    [result.arms]
  );

  /** O custo de **rodar** cada mecanismo, rodada a rodada. Fica de fora da
   * maquinaria de recortes de propósito: é tempo de parede, e não há parcela
   * dele que pertença a uma coorte ou a um perfil. Vazio em comparação gravada
   * antes de 14/11/2026, e aí a seção inteira não aparece. */
  const allocationTimes: AllocationTimeLine[] = useMemo(
    () =>
      arms
        .map((arm) => ({
          ...arm,
          seconds:
            result.arms.find((entry) => entry.key === arm.key)?.allocation_seconds ?? [],
        }))
        .filter((line) => line.seconds.length > 0),
    [arms, result.arms]
  );

  /** Os recortes da oferta que esta comparação traz. Comparação sem leilão —
   * ou gravada antes de 14/11/2026 — não traz nenhum, e a seção some. */
  const priceCuts = CLASS_CUTS.filter((option) =>
    result.arms.some((arm) =>
      arm.class_prices?.some((cut) => cut.axis === option.axis && cut.groups.length)
    )
  );
  const priceCut: ClassCut =
    priceCuts.some((option) => option.axis === priceCutChoice)
      ? priceCutChoice
      : (priceCuts[0]?.axis ?? "curriculum_period");

  /** As cores do recorte da oferta. Elas saem da paleta categórica, e não de
   * `cutGroups`, porque os grupos aqui são da grade e não da população. */
  const priceGroups: SeriesGroupStyle[] = useMemo(() => {
    const present = [
      ...new Set(
        result.arms.flatMap(
          (arm) =>
            arm.class_prices
              ?.find((cut) => cut.axis === priceCut)
              ?.groups.map((group) => group.group) ?? []
        )
      ),
    ];
    const labels = present.map((key) => classGroupLabel(priceCut, key));
    const colors = categoricalColors(labels, dark);
    return present.map((key, index) => ({
      key,
      label: labels[index],
      color: colors[labels[index]],
    }));
  }, [result.arms, priceCut, dark]);

  /** As linhas do preço: um grupo da oferta sob um modelo. Mesma forma das
   * demais séries, então o mesmo `SeriesChart` as desenha. */
  const priceLines: SeriesLine[] = arms.flatMap((arm) =>
    (
      result.arms
        .find((entry) => entry.key === arm.key)
        ?.class_prices?.find((cut) => cut.axis === priceCut)?.groups ?? []
    ).map((group) => ({
      arm: arm.key,
      group: group.group,
      points: pointsOf(group).flatMap((x, i) => {
        const band = group.values.mean_price?.[i];
        return band
          ? [{ x, q1: band[0], median: band[1], q3: band[2], n: group.n[i] }]
          : [];
      }),
    }))
  );

  /** As séries de cada braço, por recorte. */
  const series = useMemo(
    () =>
      Object.fromEntries(
        arms.map((arm) => [
          arm.key,
          seriesOf(result.arms.find((a) => a.key === arm.key)),
        ])
      ),
    [arms, result.arms]
  );

  /** As réguas que esta comparação traz. Uma gravada antes de a régua ser
   * escolha só tem a do período, e os outros botões somem. */
  const rulers = RULERS.filter((option) =>
    Object.values(series).some((axes) =>
      axes.some((a) => rulerOf(a) === option.ruler && a.groups.length)
    )
  );
  const ruler = rulers.some((r) => r.ruler === rulerChoice)
    ? rulerChoice
    : (rulers[0]?.ruler ?? "period");
  const scale = RULERS.find((option) => option.ruler === ruler) ?? RULERS[0];

  /** Os eixos de todos os braços nesta régua — o material de que saem os
   * recortes disponíveis e as linhas da amplitude. */
  const rulerAxes = useMemo(
    () => Object.values(series).flat().filter((a) => rulerOf(a) === ruler),
    [series, ruler]
  );

  /** Os eixos de perfil que a amplitude mede nesta régua. Vazio, o botão
   * "Amplitude" some: sem dois grupos não há vão. */
  const amplitudeStyles = useMemo(() => amplitudeGroups(rulerAxes), [rulerAxes]);

  /** Os recortes que esta comparação traz **nesta régua**. Uma gravada antes
   * dos recortes por perfil só tem o "Geral", e os outros botões somem. */
  const cuts = CUTS.filter((option) =>
    option.axis === AMPLITUDE
      ? amplitudeStyles.length > 0
      : rulerAxes.some((a) => a.axis === option.axis && a.groups.length)
  );
  const cut: CutChoice = cuts.some((c) => c.axis === cutChoice)
    ? cutChoice
    : (cuts[0]?.axis ?? "overall");

  /** O eixo de um braço na régua e no recorte escolhidos. */
  const axisOf = (armKey: string) =>
    series[armKey]?.find((a) => rulerOf(a) === ruler && a.axis === cut);

  /** Os grupos do recorte, com cor e rótulo. Na amplitude eles são os eixos,
   * e a cor é do eixo. */
  const groups = useMemo(() => {
    if (cut === AMPLITUDE) return amplitudeStyles;
    const present = [
      ...new Set(
        rulerAxes.flatMap(
          (axis) => (axis.axis === cut ? axis.groups.map((g) => g.group) : [])
        )
      ),
    ];
    return cutGroups(cut, run.config, present, { solo: soloColor(dark) });
  }, [rulerAxes, amplitudeStyles, cut, run.config, dark]);

  /** A seção da economia só aparece com leilão na comparação **e** com dado
   * dela: as gravadas antes de 14/11/2026 não a têm, e um gráfico vazio diria
   * menos que seção nenhuma. */
  const hasCredits = Object.values(series).some((axes) =>
    axes.some((axis) =>
      axis.groups.some((group) =>
        group.values.credits_supply?.some((band) => band !== null)
      )
    )
  );

  /** As linhas de uma grandeza: um grupo do recorte sob um modelo — ou, na
   * amplitude, um eixo de perfil sob um modelo. */
  const linesOf = (key: string): SeriesLine[] =>
    cut === AMPLITUDE
      ? arms.flatMap((arm) =>
          amplitudeLines(
            series[arm.key]?.filter((a) => rulerOf(a) === ruler) ?? [],
            arm.key,
            key
          )
        )
      : arms.flatMap((arm) =>
          (axisOf(arm.key)?.groups ?? []).map((group) => ({
            arm: arm.key,
            group: group.group,
            points: pointsOf(group).flatMap((x, i) => {
              const band = group.values[key]?.[i];
              return band
                ? [{ x, q1: band[0], median: band[1], q3: band[2], n: group.n[i] }]
                : [];
            }),
          }))
        );

  /** As execuções de um braço, na ordem das seeds. Execuções gravadas antes de
   * um braço existir simplesmente não o trazem, e o braço sai vazio em vez de
   * derrubar a tela. */
  const runsOf = (key: string): RunSummary[] =>
    result.arms.find((arm) => arm.key === key)?.runs ?? [];

  /** As duas distribuições de entrada do cenário. Não variam entre braços nem
   * entre seeds: são do cenário, não da simulação. */
  const scenarioHistograms = [
    result.grade_distribution?.length ? (
      <Histogram
        key="notas"
        title="Notas de primeira tentativa"
        fractions={result.grade_distribution}
        domain={[0, 10]}
      />
    ) : null,
    result.interest_distribution?.length ? (
      <Histogram
        key="interesse"
        title="Interesse"
        fractions={result.interest_distribution}
      />
    ) : null,
  ].filter(Boolean);

  /** Quantas rodadas o cenário teve, lido do próprio resultado. Comparações
   * gravadas antes da saturação existir não trazem a lista, e aí a seção some
   * em vez de aparecer vazia. */
  const rounds = useMemo(
    () =>
      Math.max(
        0,
        ...result.arms.flatMap((arm) =>
          arm.runs.map((entry) => entry.allocations_per_round?.length ?? 0)
        )
      ),
    [result.arms]
  );
  const saturation = useMemo(() => roundMetrics(rounds), [rounds]);

  /** Os valores de uma métrica numa amostra. Posições nulas (ninguém concluiu,
   * rodada sem o que medir) ficam de fora — zero ali seria um valor medido. */
  const valuesOf = (key: string, metric: Metric): number[] =>
    runsOf(key)
      .map(metric.of)
      .filter((value): value is number => value !== null && value !== undefined);

  /** Comparação pareada entre dois braços: em quantas das N seeds o primeiro
   * saiu melhor que o segundo. Só faz sentido porque as listas compartilham a
   * seed — é a mesma população dos dois lados, e a comparação par a par não
   * precisa supor nada sobre a forma das distribuições. Pares incompletos não
   * contam nem a favor nem contra. */
  const paired = (metric: Metric, aKey: string, bKey: string) => {
    if (metric.betterWhen === null) return null;
    const a = runsOf(aKey);
    const b = runsOf(bKey);
    let favour = 0;
    let comparable = 0;
    a.forEach((left, i) => {
      const right = b[i];
      if (!right) return;
      const x = metric.of(left);
      const y = metric.of(right);
      if (x === null || y === null) return;
      comparable++;
      if (metric.betterWhen === "higher" ? x > y : x < y) favour++;
    });
    return { favour, comparable };
  };

  /** Quantas seeds o acúmulo fez *subir* — contagem descritiva, sem juízo de
   * melhor ou pior, porque para λ e para a saturação não há um lado bom. */
  const raisedByAccumulation = (metric: Metric) => {
    const a = runsOf(WITH_ACCUMULATION);
    const b = runsOf(WITHOUT_ACCUMULATION);
    let up = 0;
    let comparable = 0;
    a.forEach((left, i) => {
      const right = b[i];
      if (!right) return;
      const x = metric.of(left);
      const y = metric.of(right);
      if (x === null || y === null) return;
      comparable++;
      if (x > y) up++;
    });
    return { up, comparable };
  };

  const medianOf = (key: string, metric: Metric) =>
    boxStats(valuesOf(key, metric))?.median ?? null;

  /** Uma linha por braço na tabela de resumo — só os que rodaram, porque uma
   * linha inteira em traços não diz nada sobre o modelo que ficou de fora. */
  const summaryRows = (metric: Metric) =>
    COMPARISON_ARMS.filter((arm) =>
      result.arms.some((entry) => entry.key === arm.key)
    ).map((arm, index) => {
      const box = boxStats(valuesOf(arm.key, metric));
      const baseline = medianOf(BASELINE, metric);
      const pairing = arm.key === BASELINE ? null : paired(metric, arm.key, BASELINE);
      return (
        <tr key={`${metric.id}-${arm.key}`}>
          {/* O nome da métrica só na primeira linha do bloco: repetido ele
              viraria ruído entre números que se comparam. */}
          <td>{index === 0 ? metric.short : ""}</td>
          <td>
            <LineSample dash={arm.dash} color={ink.secondary} /> {arm.label}
          </td>
          <td>{box ? metric.format(box.min) : "—"}</td>
          <td>{box ? metric.format(box.q1) : "—"}</td>
          <td>{box ? metric.format(box.median) : "—"}</td>
          <td>{box ? metric.format(box.q3) : "—"}</td>
          <td>{box ? metric.format(box.max) : "—"}</td>
          <td>
            {arm.key === BASELINE || box === null || baseline === null
              ? ""
              : metric.betterWhen === null
                ? "—"
                : formatDelta(box.median - baseline, metric.format)}
          </td>
          <td>
            {arm.key === BASELINE
              ? ""
              : pairing
                ? `${pairing.favour}/${pairing.comparable}`
                : "—"}
          </td>
        </tr>
      );
    });

  /** Uma linha por métrica na tabela do efeito do acúmulo. */
  const accumulationRow = (metric: Metric) => {
    const flat = medianOf(WITHOUT_ACCUMULATION, metric);
    const accumulated = medianOf(WITH_ACCUMULATION, metric);
    const baseline = medianOf(BASELINE, metric);
    const { up, comparable } = raisedByAccumulation(metric);
    return (
      <tr key={metric.id}>
        <td>{metric.short}</td>
        <td>{flat === null ? "—" : metric.format(flat)}</td>
        <td>{accumulated === null ? "—" : metric.format(accumulated)}</td>
        <td>
          {flat === null || accumulated === null
            ? "—"
            : formatDelta(accumulated - flat, metric.format)}
        </td>
        <td>{`${up}/${comparable}`}</td>
        <td className="muted-cell">{baseline === null ? "—" : metric.format(baseline)}</td>
      </tr>
    );
  };

  /** Um gráfico de séries por período, no recorte escolhido. */
  const chart = (
    id: string,
    title: string,
    key: string,
    extra: {
      bounds?: [number, number];
      format?: (value: number) => string;
      zeroLine?: boolean;
      accent?: string;
    } = {}
  ) => (
    <SeriesChart
      key={id}
      title={title}
      lines={linesOf(key)}
      groups={groups}
      arms={arms}
      runs={result.runs}
      xLabel={scale.point}
      {...extra}
      {...(cut === AMPLITUDE ? AMPLITUDE_CHART : {})}
    />
  );

  const metricChart = (metric: Metric) =>
    metric.band
      ? chart(metric.id, metric.title, metric.band, {
          bounds: metric.bounds,
          format: metric.format,
          zeroLine: metric.zeroLine,
        })
      : null;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Comparação de {formatRunDate(run.at)}</h1>
          <p className="note">{describeComparison(run)}</p>
        </div>
        <button className="secondary" onClick={onReuseConfig}>
          Reabrir esta configuração
        </button>
      </div>

      <div className="panel panel-switch">
        <h2>
          {result.runs} simulações de cada modelo — {result.runs * result.arms.length}{" "}
          simulações
        </h2>
        <div className="switch-set">
          {rulers.length > 1 && (
            <div className="switch-group" role="group" aria-label="Eixo">
              <span>Eixo</span>
              <div className="view-switch">
                {rulers.map((option) => (
                  <button
                    key={option.ruler}
                    type="button"
                    className={ruler === option.ruler ? "on" : ""}
                    aria-pressed={ruler === option.ruler}
                    onClick={() => setRuler(option.ruler)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          )}
          {cuts.length > 1 && (
            <div className="switch-group" role="group" aria-label="Linhas">
              <span>Linhas</span>
              <div className="view-switch">
                {cuts.map((option) => (
                  <button
                    key={option.axis}
                    type="button"
                    className={cut === option.axis ? "on" : ""}
                    aria-pressed={cut === option.axis}
                    onClick={() => setCut(option.axis)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <section className="chart-section">
        <header className="chart-section-head">
          <h2>Métricas de alocação</h2>
          <p>
            {cut === AMPLITUDE
              ? "O vão entre o grupo que mais colheu e o que menos colheu em cada eixo de perfil, ponto a ponto. "
              : "A mediana entre as simulações em cada ponto do eixo, com o intervalo interquartil em faixa. "}
            O tempo de formatura não entra: é da simulação inteira, não de um
            ponto dela.
          </p>
        </header>
        <div className="chart-grid">
          {METRICS.map(metricChart)}
          {/* O peso de cada ponto, no fim da grade. Ele mostra as três fases
              do horizonte — a universidade enchendo, o estado estacionário e
              a drenagem —, e sem ele a queda das curvas no fim se leria como
              mudança de mecanismo. */}
          {chart("students", scale.weight, "students", {
            bounds: [0, Infinity],
            format: formatCount,
          })}
        </div>
      </section>

      {rounds > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>Saturação da demanda</h2>
            <p>
              A mesma rodada ao longo do horizonte — a 1ª rodada de cada
              período, a 2ª de cada período —, para o decaimento se ler junto
              com o momento em que acontece.
            </p>
          </header>
          <div className="chart-grid">{saturation.map(metricChart)}</div>
        </section>
      )}

      <section className="chart-section">
        <header className="chart-section-head">
          <h2>Solicitações de disciplinas</h2>
          <p>
            O funil de cada disciplina que ainda falta ao aluno, fração a
            fração: quanto ele pediu do que lhe faltava, quanto do que pediu
            lhe foi deferido, quanto do que levou chegou a cursar e quanto do
            que cursou aprovou. Cada uma divide pelo nó anterior, de modo que
            as quatro vão de 0 a 1 e cada painel se mexe só quando o nó dele
            se mexe.
          </p>
        </header>
        <div className="chart-grid">
          {FUNNEL.map((share) =>
            chart(share.key, share.title, share.key, {
              bounds: [0, 1],
              format: formatRatio,
            })
          )}
        </div>
      </section>

      {scenarioHistograms.length > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>As distribuições do cenário</h2>
          </header>
          <div className="chart-grid">{scenarioHistograms}</div>
        </section>
      )}

      {allocationTimes.length > 0 && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>O custo de rodar o mecanismo</h2>
          </header>
          <div className="chart-grid">
            <AllocationTimeChart
              title="Tempo de alocação por rodada (escala log)"
              lines={allocationTimes}
            />
          </div>
        </section>
      )}

      {hasCredits && (
        <section className="chart-section">
          <header className="chart-section-head">
            <h2>Economia de créditos</h2>
          </header>
          <div className="chart-grid">{CREDIT_METRICS.map(metricChart)}</div>

          {priceCuts.length > 0 && (
            <>
              {priceCuts.length > 1 && (
                <div className="switch-group" role="group" aria-label="Linhas do preço">
                  <span>Linhas</span>
                  <div className="view-switch">
                    {priceCuts.map((option) => (
                      <button
                        key={option.axis}
                        type="button"
                        className={priceCut === option.axis ? "on" : ""}
                        aria-pressed={priceCut === option.axis}
                        onClick={() => setPriceCut(option.axis)}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="chart-grid">
                <SeriesChart
                  title="Preço das disciplinas"
                  lines={priceLines}
                  groups={priceGroups}
                  arms={arms}
                  runs={result.runs}
                  xLabel={RULERS[0].point}
                  bounds={[0, Infinity]}
                  format={formatCount}
                />
              </div>
            </>
          )}
        </section>
      )}

      {hasBothAuctions && (
      <div className="panel">
        <h2>O que o acúmulo de créditos muda</h2>
        <table>
          <thead>
            <tr>
              <th>Métrica</th>
              <th>Igualitário</th>
              <th>Acumulativo</th>
              <th>Efeito do acúmulo</th>
              <th>Subiu em</th>
              <th>CR (referência)</th>
            </tr>
          </thead>
          <tbody>{[...METRICS, ...saturation].map(accumulationRow)}</tbody>
        </table>
      </div>
      )}

      <div className="panel">
        <h2>Resumo das distribuições</h2>
        <table>
          <thead>
            <tr>
              <th>Métrica</th>
              <th>Modelo</th>
              <th>Mín</th>
              <th>1º quartil</th>
              <th>Mediana</th>
              <th>3º quartil</th>
              <th>Máx</th>
              <th>Diferença</th>
              <th>Seeds a favor</th>
            </tr>
          </thead>
          <tbody>{[...METRICS, ...saturation].flatMap(summaryRows)}</tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Simulação a simulação</h2>
        <table>
          <thead>
            <tr>
              <th>Seed</th>
              <th>Períodos</th>
              <th>Formados</th>
              {METRICS.map((metric) => (
                <th key={metric.id}>{metric.short}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: result.runs }, (_, i) => {
              const row = arms.map((arm) => runsOf(arm.key)[i]).filter(Boolean);
              if (!row.length) return null;
              const join = (
                of: (run: RunSummary) => number | null,
                format: (value: number) => string
              ) =>
                row
                  .map((entry) => {
                    const value = of(entry);
                    return value === null ? "—" : format(value);
                  })
                  .join(" / ");
              const periods = [...new Set(row.map((entry) => entry.periods))];
              return (
                <tr key={row[0].seed}>
                  <td>{row[0].seed}</td>
                  <td>{periods.length === 1 ? periods[0] : periods.join(" / ")}</td>
                  <td>{join((entry) => entry.graduates, formatCount)}</td>
                  {METRICS.map((metric) => (
                    <td key={metric.id}>{join(metric.of, metric.format)}</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Por último, o caso individual. Tudo acima é agregado — a distribuição
          entre as simulações e o perfil dentro delas —, e esta seção é a porta
          de saída para o outro extremo: um aluno, uma disciplina, uma rodada.
          Fica no fim porque custa uma simulação a mais, e porque a pergunta
          que ela responde ("por que este número saiu assim?") só aparece
          depois de ver o número. */}
      <Trace run={run} />
    </div>
  );
}
