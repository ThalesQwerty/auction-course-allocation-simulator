/** A densidade da Beta num grid de nós, para integrar sem função gama.
 *
 *     f(a) ∝ a^(α−1) · (1 − a)^(β−1)
 *
 * Os pesos são normalizados pela própria soma, o que dispensa a constante
 * B(α, β) — e, com ela, uma função gama. Os nós saem em `ln a` porque é assim
 * que `approvalShare` os consome.
 *
 * **Com as duas formas ≥ 1** a densidade é limitada e um grid uniforme de
 * pontos médios integra bem.
 *
 * **Abaixo de 1 ela diverge na ponta**, e divergir aqui é o caso comum, não o
 * exótico: com média 0,67 a segunda forma passa abaixo de 1 assim que a
 * concentração cai abaixo de 3. O grid uniforme então perde a massa encostada
 * na parede e o gráfico mente sobre a própria média — em concentração 1 ele
 * desenhava nota média 6,57 onde o modelo entrega 6,70; em 0,5, 6,20 contra
 * 6,70.
 *
 * O conserto é integrar na variável em que o integrando é liso. No ramo de
 * baixo, `a = corte · u^(1/α)`: o jacobiano cancela exatamente o `a^(α−1)` que
 * diverge em 0. No de cima, `1 − a = (1 − corte) · v^(1/β)`, idem para o
 * `(1 − a)^(β−1)` que diverge em 1. Sobra integrando limitado dos dois lados,
 * e a média volta a sair exata em qualquer concentração.
 */
export interface QuadratureNode {
  logA: number;
  weight: number;
}

/** Nós da quadratura. Alto porque o integrando é barato e o desenho não pode
 * tremer a cada tecla. */
const NODES = 3000;

/** Onde o grid se parte em dois ramos, quando precisa partir. */
const SPLIT = 0.5;

export function betaQuadrature(alpha: number, beta: number): QuadratureNode[] {
  const nodes: QuadratureNode[] = [];
  let total = 0;
  const push = (a: number, weight: number) => {
    nodes.push({ logA: Math.log(a), weight });
    total += weight;
  };

  if (alpha >= 1 && beta >= 1) {
    for (let i = 0; i < NODES; i++) {
      const a = (i + 0.5) / NODES;
      push(a, Math.exp((alpha - 1) * Math.log(a) + (beta - 1) * Math.log(1 - a)));
    }
  } else {
    const half = NODES / 2;
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
