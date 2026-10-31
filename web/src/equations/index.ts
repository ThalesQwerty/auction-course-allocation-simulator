/** Uma fórmula por arquivo, uma função pura por fórmula.
 *
 * O espelho de `src/leilao/equations/` no navegador. Nem tudo aqui tem
 * contraparte lá, e vice-versa: a tela precisa de contas que o motor não faz
 * (a densidade em forma fechada, a leitura estatística de uma amostra) e não
 * precisa das que ele faz (a alocação em si).
 *
 * O que **é** duplicado — a forma da Beta, a amostra de utilidade, as duas
 * induções sobre a grade — é duplicado de propósito: a prévia desenha a
 * distribuição que os parâmetros produzem **antes** de existir execução a
 * quem perguntar. Quando a conta muda no motor, muda aqui também.
 *
 * ÍNDICE
 * ------
 *
 * Prévia das notas
 *     betaShape          forma da Beta a partir de média e concentração
 *     gradeExponent      E = D / (u_rel^g_u · tentativas)
 *     gradeDensity       densidade da nota, por mudança de variável
 *     betaQuadrature     densidade da Beta num grid, para integrar
 *     approvalShare      a fração que alcança n_min
 *
 * Prévia das utilidades
 *     mulberry32             gerador de semente fixa
 *     relativeUtilitySample  log-normal normalizada, em múltiplos da indiferença
 *     kernelSmooth           núcleo gaussiano com reflexão nas bordas
 *
 * Leitura de uma curva ou de uma amostra
 *     densityCurve       área 1, acumulada e moda
 *     quantile           método 7 (R e numpy)
 *     boxStats           cinco números e as cercas de Tukey
 *     niceScale          domínio e marcas legíveis
 *     paddedScale        a régua de um gráfico: o contradomínio, ou os dados
 *
 * A grade
 *     induct             a travessia das duas induções
 *     curriculumPeriods  o período induzido dos pré-requisitos
 *     curriculumHeights  a altura na DAG de sucessores
 */
export { approvalShare } from "./approvalShare";
export { betaQuadrature } from "./betaQuadrature";
export { betaShape } from "./betaShape";
export { boxStats } from "./boxStats";
export type { BoxStats } from "./boxStats";
export { CYCLIC, curriculumPeriods } from "./curriculumPeriods";
export { HEIGHT_CYCLE, curriculumHeights } from "./curriculumHeights";
export { densityCurve } from "./densityCurve";
export type { Curve, DensityPoint } from "./densityCurve";
export { gradeDensity } from "./gradeDensity";
export { gradeExponent } from "./gradeExponent";
export { induct } from "./induct";
export { kernelSmooth } from "./kernelSmooth";
export { mulberry32 } from "./mulberry32";
export { niceScale } from "./niceScale";
export { paddedScale } from "./paddedScale";
export type { Scale } from "./paddedScale";
export { quantile } from "./quantile";
export { relativeUtilitySample } from "./relativeUtilitySample";
