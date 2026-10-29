/** Domínio e marcas arredondados a passos legíveis.
 *
 *     passo = {1, 2, 2,5, 5 ou 10} × 10^⌊log₁₀((alto − baixo)/n)⌋
 *     de = ⌊baixo/passo⌋ · passo,   até = ⌈alto/passo⌉ · passo
 *
 * O conjunto de multiplicadores é o que produz marcas que uma pessoa lê sem
 * contar casas: 0,25 · 0,5 · 0,75 em vez de 0,23 · 0,47 · 0,70. O domínio é
 * então **estendido** até cobrir os dados, e não o contrário — uma caixa não
 * pode sair pela borda do gráfico.
 *
 * Amostra sem dispersão (todas as execuções iguais) não tem escala: abre-se
 * uma folga de 5% em torno do valor para a linha não ficar colada no eixo.
 */
const STEPS = [1, 2, 2.5, 5, 10];
const FLAT_PADDING = 0.05;

export function niceScale(low: number, high: number, count = 4) {
  if (!(high > low)) {
    const pad = Math.abs(high) * FLAT_PADDING || FLAT_PADDING;
    low = high - pad;
    high = high + pad;
  }
  const rough = (high - low) / count;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const normalized = rough / magnitude;
  const step = (STEPS.find((candidate) => normalized <= candidate) ?? 10) * magnitude;

  const from = Math.floor(low / step) * step;
  const to = Math.ceil(high / step) * step;
  const ticks: number[] = [];
  for (let i = 0; from + i * step <= to + step / 2; i++) ticks.push(from + i * step);
  return { from, to: ticks[ticks.length - 1], ticks };
}
