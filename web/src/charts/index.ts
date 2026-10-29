/** Os gráficos: tema, formatos e as três marcas que a interface usa.
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
export { formatCount, formatRatio } from "./format";
export { SeriesTip } from "./SeriesTip";
export { STATUS, categoricalColors, inkFor, soloColor, usePrefersDark } from "./theme";
export type { Ink } from "./theme";
