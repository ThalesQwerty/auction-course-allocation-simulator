/** Os gráficos: tema, formatos e as marcas que a interface usa.
 *
 * A comparação lê tudo por **período**: a série põe o período num eixo
 * ordenado e mostra, por grupo e por modelo, a mediana entre as simulações e
 * o intervalo interquartil.
 *
 * A **estatística** por trás deles não mora aqui — a régua de marcas legíveis
 * e os quantis estão em `equations/`, onde se revisam como fórmula. Aqui fica
 * o desenho.
 */
export { DensityChart } from "./DensityChart";
export type { DensitySplit } from "./DensityChart";
export { Histogram } from "./Histogram";
export { LineSample, SeriesChart } from "./SeriesChart";
export type {
  BandPoint,
  SeriesArmStyle,
  SeriesGroupStyle,
  SeriesLine,
} from "./SeriesChart";
export { formatCount, formatRatio } from "./format";
export { SeriesTip } from "./SeriesTip";
export {
  REQUEST_STATES,
  STATUS,
  categoricalColors,
  inkFor,
  requestStateColors,
  soloColor,
  usePrefersDark,
} from "./theme";
export type { Ink } from "./theme";
