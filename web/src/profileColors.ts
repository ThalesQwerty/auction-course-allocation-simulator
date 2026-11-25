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

export const MAX_BANDS = 5;
/** Daí o teto de cortes: `q` cortes abrem `q + 1` faixas. Espelha
 * `leilao.config.MAX_CUTS`. */
export const MAX_CUTS = MAX_BANDS - 1;

/** A cor da faixa de índice `band` (0 é a mais **baixa**) numa escada de
 * `bands` faixas.
 *
 * O índice vem de baixo porque é assim que a API ordena as faixas; a rampa
 * está escrita de cima para baixo porque é assim que ela se lê. */
export const bandColor = (band: number, bands: number): string => {
  const ramp = RAMPS[Math.min(Math.max(bands, 1), MAX_BANDS)] ?? RAMPS[1];
  return ramp[ramp.length - 1 - band] ?? ramp[ramp.length - 1];
};

/** AS CORES ESCOLHIDAS PELO USUÁRIO
 * =================================
 *
 * A rampa acima continua sendo o padrão; o que vem daqui a sobrepõe posição a
 * posição. Mora no `localStorage`, e **não** no cenário: a cor não entra em
 * conta nenhuma, então mandá-la no `CompareRequest` faria o motor carregar
 * dado de apresentação. O preço é que ela não viaja com o cenário exportado.
 *
 * A chave é o eixo, e o valor é uma cor por faixa, indexada **de baixo para
 * cima** — a mesma ordem em que a API lista as faixas. Uma posição vazia cai
 * na rampa, de modo que escolher a cor de uma faixa não repinta as outras.
 */
const COLOR_KEY = "leilao:band-colors";

type BandColors = Record<string, (string | undefined)[]>;

/** Lê o mapa inteiro. Volta vazio se o navegador recusar o acesso — janela
 * anônima, dado do site bloqueado — ou se o conteúdo não for o que se espera:
 * a tela tem de desenhar com a rampa padrão em vez de quebrar. */
export function readBandColors(): BandColors {
  try {
    const raw = window.localStorage.getItem(COLOR_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed as Record<string, unknown>)
        .filter(([, value]) => Array.isArray(value))
        .map(([axis, value]) => [
          axis,
          (value as unknown[]).map((color) =>
            typeof color === "string" && /^#[0-9a-fA-F]{6}$/.test(color)
              ? color
              : undefined
          ),
        ])
    );
  } catch {
    return {};
  }
}

/** Grava a cor de uma faixa. `color` nulo devolve a posição à rampa. */
export function writeBandColor(
  axis: string,
  band: number,
  color: string | null
): BandColors {
  const all = readBandColors();
  const colors = [...(all[axis] ?? [])];
  while (colors.length <= band) colors.push(undefined);
  colors[band] = color ?? undefined;
  const next = { ...all, [axis]: colors };
  try {
    window.localStorage.setItem(COLOR_KEY, JSON.stringify(next));
  } catch {
    // Sem onde gravar, a escolha vale só para esta sessão: o estado em memória
    // já foi atualizado, e é ele que a tela desenha.
  }
  return next;
}
