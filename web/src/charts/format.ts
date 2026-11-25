/** Os dois formatos de número dos gráficos */
export const formatRatio = (value: number) =>
  value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const formatCount = (value: number) =>
  value.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
