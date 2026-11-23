/** As cores das faixas de quantil nos gráficos.
 *
 * A cor é **da posição**, e não do grupo: as faixas são um corte ordenado de
 * uma população contínua, da mais baixa para a mais alta, e a rampa diz essa
 * ordem. Era o contrário enquanto havia perfis declarados — lá a cor era do
 * grupo, escolhida no cenário, para que esconder um grupo não repintasse os
 * outros.
 *
 * A escada é aninhada: cada nível é o anterior com uma cor a mais no topo
 * frio. Fora dela fica o caso de **uma faixa só**, que é a universidade
 * inteira e não tem ordem a codificar — ali vale o azul de série solitária,
 * que é o mesmo `PALETTE.blue`.
 *
 * O amarelo fica abaixo de 3:1 na superfície clara (ver `charts/theme`), e a
 * mitigação prevista é rótulo em palavras ao lado: aqui ela está satisfeita
 * por construção, porque o nome da faixa é o intervalo que ela cobre.
 *
 * As cores são fixas nos dois temas, como `STATUS`, para que "faixa baixa" e
 * "reprova" não tenham duas cores no mesmo aplicativo.
 */
import { STATUS } from "./charts";

export const PALETTE = {
  gray: "#8a8984",
  red: STATUS.critical,
  orange: "#eb6834",
  yellow: STATUS.warning,
  green: STATUS.good,
  teal: "#1a9e8f",
  blue: "#2a78d6",
  violet: "#7b4fd6",
  pink: "#e0679a",
  brown: "#8b5a2b",
} as const;

/** A rampa de cada número de faixas, **do mais alto para o mais baixo** — que
 * é a ordem em que a legenda as lista. */
const RAMPS: Record<number, string[]> = {
  1: [PALETTE.blue],
  2: [PALETTE.green, PALETTE.red],
  3: [PALETTE.green, PALETTE.yellow, PALETTE.red],
  4: [PALETTE.blue, PALETTE.green, PALETTE.yellow, PALETTE.red],
  5: [PALETTE.violet, PALETTE.blue, PALETTE.green, PALETTE.yellow, PALETTE.red],
};

export const MAX_QUANTILES = 5;

/** A cor da faixa de índice `band` (0 é a mais **baixa**) numa escada de
 * `bands` faixas.
 *
 * O índice vem de baixo porque é assim que a API ordena as faixas; a rampa
 * está escrita de cima para baixo porque é assim que ela se lê. */
export const bandColor = (band: number, bands: number): string => {
  const ramp = RAMPS[Math.min(Math.max(bands, 1), MAX_QUANTILES)] ?? RAMPS[1];
  return ramp[ramp.length - 1 - band] ?? ramp[ramp.length - 1];
};
