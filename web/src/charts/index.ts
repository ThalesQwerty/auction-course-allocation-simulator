/** Os gráficos: tema, formatos e as marcas que a interface usa */
export { AllocationTimeChart, formatSeconds } from "./AllocationTimeChart";
export type { AllocationTimeLine } from "./AllocationTimeChart";
export { BoxPlot } from "./BoxPlot";
export type { BoxRow } from "./BoxPlot";
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
  STATUS,
  categoricalColors,
  inkFor,
  soloColor,
  usePrefersDark,
} from "./theme";
export type { Ink } from "./theme";
