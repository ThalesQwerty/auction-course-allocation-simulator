/** Prévia das duas distribuições de entrada do cenário, calculada no navegador
 * enquanto o usuário edita os parâmetros.
 *
 * Aqui não há dados: o que a tela desenha é a **forma que os parâmetros
 * produzem**, antes de existir execução alguma. Por isso são curvas de
 * densidade, e não os histogramas da tela de resultados — lá as barras contam
 * o que de fato aconteceu. A conta é duplicada do motor de propósito, pelo
 * mesmo motivo de `curriculum.ts`: a tela precisa do número antes de ter a
 * quem perguntar.
 */
import type { Scenario } from "./types";

/** A curva das notas é **quadratura**, não sorteio: a aptidão entra como
 * densidade num grid fino e o resto da fórmula é determinístico. Assim o
 * gráfico não treme a cada tecla, e um parâmetro que mal muda a distribuição
 * mal muda o desenho. */
const APTITUDE_NODES = 3000;

/** Média e concentração, como a interface as edita, nos dois parâmetros de
 * forma que a Beta pede — a mesma conversão que o motor faz na entrada
 * (`grading.beta_shape`). */
const betaShape = (mean: number, concentration: number): [number, number] => [
  mean * concentration,
  (1 - mean) * concentration,
];

/** Onde o grid se parte em dois ramos, quando precisa partir. */
const SPLIT = 0.5;

/** A densidade da Beta num grid de pontos, normalizada pela própria soma — o
 * que dispensa a constante B(α, β) e, com ela, uma função gama.
 *
 * **Com as duas formas >= 1** a densidade é limitada e um grid uniforme de
 * pontos médios integra bem.
 *
 * **Abaixo de 1 ela diverge na ponta**, e divergir aqui é o caso comum, não o
 * exótico: com média 0,67 a segunda forma passa abaixo de 1 assim que a
 * concentração cai abaixo de 3. O grid uniforme então perde a massa encostada
 * na parede e o gráfico mente sobre a própria média — em concentração 1 ele
 * desenhava nota média 6,57 onde o modelo entrega 6,70, e em 0,5 desenhava
 * 6,20 contra 6,70.
 *
 * O conserto é integrar na variável em que o integrando é liso. No ramo de
 * baixo, `a = corte · u^(1/α)`: o jacobiano cancela exatamente o `a^(α−1)`
 * que diverge em 0. No de cima, `1 − a = (1 − corte) · v^(1/β)`, idem para o
 * `(1 − a)^(β−1)` que diverge em 1. Sobra integrando limitado dos dois lados,
 * e a média volta a sair exata em qualquer concentração. */
function aptitudeNodes(alpha: number, beta: number): { logA: number; weight: number }[] {
  const nodes: { logA: number; weight: number }[] = [];
  let total = 0;
  const push = (a: number, weight: number) => {
    nodes.push({ logA: Math.log(a), weight });
    total += weight;
  };

  if (alpha >= 1 && beta >= 1) {
    for (let i = 0; i < APTITUDE_NODES; i++) {
      const a = (i + 0.5) / APTITUDE_NODES;
      push(a, Math.exp((alpha - 1) * Math.log(a) + (beta - 1) * Math.log(1 - a)));
    }
  } else {
    const half = APTITUDE_NODES / 2;
    const step = 1 / half;
    for (let i = 0; i < half; i++) {
      const u = (i + 0.5) * step;
      const a = SPLIT * Math.pow(u, 1 / alpha);
      push(a, Math.pow(1 - a, beta - 1) * (Math.pow(SPLIT, alpha) / alpha) * step);
    }
    for (let i = 0; i < half; i++) {
      const v = (i + 0.5) * step;
      const a = 1 - (1 - SPLIT) * Math.pow(v, 1 / beta);
      push(a, Math.pow(a, alpha - 1) * (Math.pow(1 - SPLIT, beta) / beta) * step);
    }
  }

  return total > 0
    ? nodes.map(({ logA, weight }) => ({ logA, weight: weight / total }))
    : nodes.map(({ logA }) => ({ logA, weight: 1 / nodes.length }));
}

/** O caso que a prévia das notas desenha: uma disciplina de dificuldade `D`, na
 * `t`-ésima tentativa. Não é parâmetro de cenário — é o recorte que se escolhe
 * para olhar, e por isso vive na tela e não em `Scenario`. */
export interface GradeCase {
  difficulty: number;
  attempt: number;
  /** A **utilidade relativa** da disciplina para o aluno: a fração de
   * utilidade vezes o número de disciplinas, de modo que 1 é o aluno
   * indiferente e 2 é querer o dobro da média. Só morde quando o ganho por
   * utilidade do cenário é maior que zero, porque é como expoente dele que ela
   * entra. */
  relativeUtility: number;
}

/** Um ponto da curva. `cum` é a massa acumulada até ali — é o número que o
 * gráfico mostra no mouse, porque a altura de uma densidade não se lê. */
export interface DensityPoint {
  x: number;
  y: number;
  cum: number;
}

/** Uma curva pronta para desenhar, com os dois números que o rodapé mostra. */
export interface Curve {
  points: DensityPoint[];
  /** Onde a densidade é máxima — o valor mais provável. */
  mode: number;
}

/** Quantos pontos a curva leva para a tela. */
const CURVE_POINTS = 120;

/** A curva das notas anda de **um décimo**, que é a grade em que o motor
 * entrega a nota (`round(100 · a^expoente)/10`). Assim todo ponto do desenho é
 * uma nota que a simulação pode de fato produzir, e o que o mouse mostra tem o
 * mesmo arredondamento do relatório. */
const GRADE_POINTS = 101;

/** A curva das notas de uma disciplina de dificuldade `D` na `t`-ésima
 * tentativa, sobre a escala inteira de 0 a 10.
 *
 * A nota é `round(100 · a^expoente)/10` com `expoente = D / (u_rel^ganho ·
 * tentativas)` — a fórmula de `grade_for_attempt`. Como ela é **monótona** na
 * aptidão e nada mais é sorteado, a densidade sai em forma fechada, pela
 * mudança de variável: com `a = (g/10)^(1/E)`, a densidade da nota é a da Beta
 * em `a` vezes `da/dg = a / (10·E·(g/10))`. Nada de amostragem e nada de
 * faixas, então a curva é lisa por construção e não treme a cada tecla.
 *
 * A **aprovação** não sai da curva: ela vem da quadratura (`aptitudeNodes`),
 * que integra certo mesmo quando a densidade diverge na ponta. Curva para a
 * forma, quadratura para o número.
 *
 * Em t > 1 o que sai é a nota que a **população inteira** tiraria naquela
 * tentativa, e não a dos recursantes: quem recursa é quem foi mal, então a
 * amostra real de uma segunda tentativa é a cauda de baixo da aptidão. Isto
 * aqui responde "quanto a tentativa vale", não "como ficou a turma de
 * repetentes". */
export function gradeDensity(
  scenario: Scenario,
  { difficulty, attempt, relativeUtility }: GradeCase
): Curve & { approval: number } {
  const [alpha, beta] = betaShape(scenario.aptitude_mean, scenario.aptitude_concentration);
  // Campo vazio vira 0, e expoente 0 daria 10 para todo mundo. O piso é da
  // prévia, não do modelo: aqui ele evita um gráfico degenerado enquanto se
  // digita; lá o motor valida o cenário.
  const d = difficulty > 0 ? difficulty : 0.1;
  // u_rel^(ganho por utilidade), como em `grade_for_attempt`: com ganho 0 o
  // fator é 1 e a utilidade relativa some da conta, que é o controle a
  // reportar ao lado de qualquer resultado em conclusões.
  const raised = relativeUtility > 0 ? Math.pow(relativeUtility, scenario.utility_gain) : 1;
  const utilityFactor = raised > 0 ? raised : 1;
  // Tentativas efetivas, como no motor: em ganho 1 isto é o próprio t.
  const attempts = Math.max(
    1e-9,
    1 + scenario.retake_gain * (Math.max(1, Math.floor(attempt)) - 1)
  );
  const exponent = d / (utilityFactor * attempts);

  const step = 10 / (GRADE_POINTS - 1);
  const raw = new Array<number>(GRADE_POINTS).fill(0);
  for (let i = 0; i < GRADE_POINTS; i++) {
    const t = (i * step) / 10;
    if (t <= 0 || t >= 1) {
      // As pontas: a nota 0 e a nota 10 só ocorrem no limite, e é lá que a
      // densidade pode divergir. A curva fecha no eixo.
      raw[i] = 0;
      continue;
    }
    const a = Math.pow(t, 1 / exponent);
    if (!(a > 0) || a >= 1) {
      raw[i] = 0;
      continue;
    }
    // Densidade da Beta vezes o jacobiano da mudança de variável. A constante
    // B(α, β) some na normalização numérica logo abaixo.
    raw[i] = Math.exp((alpha - 1) * Math.log(a) + (beta - 1) * Math.log(1 - a)) * (a / (10 * exponent * t));
  }

  const xs = raw.map((_, i) => i * step);
  return {
    ...normalize(xs, raw),
    approval: approvalShare(alpha, beta, exponent, scenario.min_grade),
  };
}

/** Fecha a curva como **densidade de probabilidade**: a área sob ela vale 1.
 *
 * A régua do eixo y é fixa em [0, 1] (ver `DensityChart`), e não acompanha a
 * curva: duas distribuições se comparam na mesma escala, e uma curva baixa se
 * lê como baixa. A densidade pode passar de 1 quando o eixo x é estreito — aí
 * o gráfico mostra até 1 e o resto fica fora da moldura; a probabilidade
 * inteira continua no acumulado, que é o que o mouse mostra. */
function normalize(xs: number[], raw: number[]): Curve {
  // Trapézio com passo variável: o grid não é uniforme quando a régua é mais
  // larga que o suporte, e aí os pontos se concentram onde a massa está.
  let area = 0;
  for (let i = 1; i < raw.length; i++) {
    area += ((raw[i] + raw[i - 1]) / 2) * (xs[i] - xs[i - 1]);
  }
  if (!(area > 0)) {
    return { points: xs.map((x) => ({ x, y: 0, cum: 0 })), mode: 0 };
  }

  const points: DensityPoint[] = [];
  let cum = 0;
  let mode = 0;
  let highest = -1;
  for (let i = 0; i < raw.length; i++) {
    const density = raw[i] / area;
    if (i > 0) cum += ((density + raw[i - 1] / area) / 2) * (xs[i] - xs[i - 1]);
    if (density > highest) {
      highest = density;
      mode = xs[i];
    }
    points.push({ x: xs[i], y: density, cum: Math.min(1, cum) });
  }
  return { points, mode };
}

/** A fração que alcança n_min, pela quadratura da aptidão: `nota >= n_min`
 * equivale a `a >= (n_min/10)^(1/E)`, porque a nota é monótona na aptidão. */
function approvalShare(alpha: number, beta: number, exponent: number, minGrade: number): number {
  const target = Math.min(1, Math.max(0, minGrade / 10));
  if (target <= 0) return 1;
  const floor = Math.pow(target, 1 / exponent);
  let share = 0;
  for (const { logA, weight } of aptitudeNodes(alpha, beta)) {
    if (Math.exp(logA) >= floor) share += weight;
  }
  return share;
}

/** Linhas sorteadas para a curva das utilidades. */
const UTILITY_ROWS = 480;

/** Células do grid fino em que a amostra é contada antes de ser suavizada. */
const FINE_CELLS = 600;


/** Largura do núcleo gaussiano, em células do grid fino. A curva da utilidade é
 * a única que vem de sorteio — não há forma fechada para a fração `x/Σx` —, e
 * sem suavizar ela sai com um serrilhado que parece dado medido. O núcleo é o
 * que a devolve ao que ela é: uma forma, não uma amostra. */
const KERNEL_CELLS = 10;

/** Semente da prévia. Ela não é a seed do cenário de propósito: o que a tela
 * mostra é a forma que os parâmetros produzem, e não a execução que virá. */
const PREVIEW_SEED = 20261029;

/** Gerador próprio, de semente fixa: a prévia precisa ser **função dos
 * parâmetros**, senão o desenho mudaria sozinho a cada render. */
function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A curva de como um aluno reparte a preferência dele, em **utilidade
 * relativa**: a fração de utilidade da disciplina vezes o número de
 * disciplinas, de modo que 1 é a indiferença e a média é exatamente 1 em
 * qualquer cenário. O eixo vai de 0 ao maior valor sorteado: é o suporte da
 * distribuição, e é ele que uma curva de densidade desenha.
 *
 * A régua da **fração** saiu em 30/10/2026. Ela mede a mesma distribuição
 * dividida por |disciplinas|, e com isso o eixo x encolhe na mesma proporção:
 * numa grade de 60 a massa inteira cabia em 4% do eixo e a densidade subia a
 * 100, o que não se lê.
 *
 * Espelha dois dos três passos de `draw_utilities`: log-normal e divisão pelo
 * somatório. O **deslocamento por altura fica de fora**, e é uma decisão de
 * leitura: ele é curricular, não populacional — ordena as camadas entre si —, e
 * domina tanto a linha que, com ele, metade das disciplinas (as de altura 0)
 * cai sozinha na primeira célula e o desenho não se mexe mais com σ.
 *
 * A estabilidade também não entra: ela reparte a variância entre a parte
 * permanente e a do semestre, e a soma das duas é sempre 1, de modo que a
 * distribuição de um período qualquer não depende dela. */
export function utilityDensity(scenario: Scenario): Curve {
  const size = scenario.disciplines.length;
  if (size < 2) return { points: [], mode: 0 };

  const random = mulberry32(PREVIEW_SEED);
  const raw = new Array<number>(size).fill(0);
  const values = new Array<number>(UTILITY_ROWS * size);
  let at = 0;
  let highest = 0;

  for (let r = 0; r < UTILITY_ROWS; r++) {
    for (let j = 0; j < size; j += 2) {
      // Box-Muller: dois normais por par de uniformes.
      const u1 = Math.max(random(), Number.MIN_VALUE);
      const u2 = random();
      const radius = Math.sqrt(-2 * Math.log(u1));
      raw[j] = Math.exp(scenario.utility_sigma * radius * Math.cos(2 * Math.PI * u2));
      if (j + 1 < size) {
        raw[j + 1] = Math.exp(scenario.utility_sigma * radius * Math.sin(2 * Math.PI * u2));
      }
    }
    let sum = 0;
    for (let j = 0; j < size; j++) sum += raw[j];
    for (let j = 0; j < size; j++) {
      // Fração da linha vezes |disciplinas|: a média sai 1, a indiferença.
      const value = (raw[j] / sum) * size;
      values[at++] = value;
      if (value > highest) highest = value;
    }
  }
  if (!(highest > 0)) return { points: [], mode: 0 };

  // Conta num grid fino...
  const counts = new Array<number>(FINE_CELLS).fill(0);
  for (const value of values) {
    counts[Math.min(FINE_CELLS - 1, Math.max(0, Math.floor((value / highest) * FINE_CELLS)))] += 1;
  }

  // ...e suaviza com um núcleo gaussiano. Nas bordas o núcleo é **refletido**
  // em vez de truncado: truncar faria a densidade afundar justamente onde esta
  // distribuição empilha massa, que é encostada no zero.
  const reach = KERNEL_CELLS * 3;
  const kernel: number[] = [];
  for (let k = -reach; k <= reach; k++) {
    kernel.push(Math.exp((-0.5 * k * k) / (KERNEL_CELLS * KERNEL_CELLS)));
  }
  const smooth = new Array<number>(FINE_CELLS).fill(0);
  for (let i = 0; i < FINE_CELLS; i++) {
    let acc = 0;
    let mass = 0;
    for (let k = -reach; k <= reach; k++) {
      let j = i + k;
      if (j < 0) j = -j - 1;
      if (j >= FINE_CELLS) j = 2 * FINE_CELLS - j - 1;
      if (j < 0 || j >= FINE_CELLS) continue;
      const w = kernel[k + reach];
      acc += counts[j] * w;
      mass += w;
    }
    smooth[i] = mass > 0 ? acc / mass : 0;
  }

  // O grid fino desce para os pontos da curva, e a área vai a 1 na saída.
  const xs: number[] = [];
  const picked: number[] = [];
  for (let i = 0; i < CURVE_POINTS; i++) {
    const cell = Math.min(FINE_CELLS - 1, Math.round((i / (CURVE_POINTS - 1)) * (FINE_CELLS - 1)));
    xs.push((highest * i) / (CURVE_POINTS - 1));
    picked.push(smooth[cell]);
  }
  return normalize(xs, picked);
}
