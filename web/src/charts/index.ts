/** Os gráficos: tema, formatos e as quatro marcas que a interface usa.
 *
 * Duas delas leem o mesmo material da comparação por eixos diferentes. O
 * **boxplot** põe os modelos num eixo categórico e mostra a distribuição de
 * uma média entre as execuções; a **série** põe o período num eixo ordenado e
 * mostra a trajetória que essa média resume. A linha só é lícita onde o eixo
 * tem ordem — sobre as seeds ela desenharia a ordem do sorteio.
 *
 * A **estatística** por trás deles não mora aqui — os cinco números do
 * boxplot, as cercas de Tukey e a régua de marcas legíveis estão em
 * `equations/`, onde se revisam como fórmula. Aqui fica o desenho.
 */
export { BoxPlot } from "./BoxPlot";
export type { BoxGroup } from "./BoxPlot";
export { DensityChart } from "./DensityChart";
export type { DensitySplit } from "./DensityChart";
export { Histogram } from "./Histogram";
export { SeriesChart } from "./SeriesChart";
export type { SeriesGroup, SeriesPoint } from "./SeriesChart";
export { formatCount, formatRatio } from "./format";
export { SeriesTip } from "./SeriesTip";
export { STATUS, categoricalColors, inkFor, soloColor, usePrefersDark } from "./theme";
export type { Ink } from "./theme";
