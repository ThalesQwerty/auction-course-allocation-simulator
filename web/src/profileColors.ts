/** As cores dos grupos de perfil nos gráficos.
 *
 * A cor é **do grupo**, escolhida no cenário, e não da posição na legenda:
 * esconder um grupo ou trocar de recorte não repinta os outros. Fixa nos dois
 * temas, como `STATUS` — vermelho, amarelo e verde são os mesmos tons, para
 * que "baixo" e "reprova" não tenham duas cores no mesmo aplicativo.
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

/** As opções do seletor, na ordem em que aparecem. */
export const PRESET_COLORS: { name: string; value: string }[] = [
  { name: "cinza", value: PALETTE.gray },
  { name: "vermelho", value: PALETTE.red },
  { name: "laranja", value: PALETTE.orange },
  { name: "amarelo", value: PALETTE.yellow },
  { name: "verde", value: PALETTE.green },
  { name: "verde-azulado", value: PALETTE.teal },
  { name: "azul", value: PALETTE.blue },
  { name: "violeta", value: PALETTE.violet },
  { name: "rosa", value: PALETTE.pink },
  { name: "marrom", value: PALETTE.brown },
];

/** A cor de reserva por posição, para perfil gravado antes de a cor existir
 * ou criado sem ela. Começa pelos três de semáforo, que é a ordem dos eixos
 * de traço (alto, médio, baixo). */
const FALLBACK = [
  PALETTE.green,
  PALETTE.yellow,
  PALETTE.red,
  PALETTE.blue,
  PALETTE.violet,
  PALETTE.orange,
  PALETTE.pink,
  PALETTE.teal,
  PALETTE.brown,
  PALETTE.gray,
];

export const profileColor = (
  profile: { color?: string },
  index: number
): string => profile.color ?? FALLBACK[index % FALLBACK.length];

/** A primeira cor da paleta que nenhum perfil do eixo usa — a do perfil
 * novo. Com todas em uso, recomeça pela posição. */
export const nextColor = (taken: { color?: string }[]): string => {
  const used = new Set(taken.map((p, i) => profileColor(p, i)));
  return FALLBACK.find((c) => !used.has(c)) ?? FALLBACK[taken.length % FALLBACK.length];
};
