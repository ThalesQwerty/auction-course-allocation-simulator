/** φ = (Σ ψ)² / (n · Σ ψ²) — equidade de Jain, anteprojeto eq. (55) */
export function jainIndex(values: number[]): number {
  if (!values.length) return 0;
  const squares = values.reduce((total, value) => total + value * value, 0);
  if (squares === 0) return 0;
  const sum = values.reduce((total, value) => total + value, 0);
  return Math.min(1, (sum * sum) / (values.length * squares));
}
