/** Indução sobre a DAG de pré-requisitos, iterativa.
 *
 * Duas grandezas da grade são a mesma recorrência sobre arestas opostas — a
 * altura anda pelos sucessores, o período pelos predecessores —, então a
 * travessia mora aqui e cada uma declara só o que a sua recorrência faz.
 *
 * Espelha `equations._induction` do motor, com uma diferença que é o ponto:
 * **ciclo aqui não é erro**. O motor recusa o cenário; a tela de configuração
 * precisa sobreviver a ele, porque um ciclo é o estado normal do formulário
 * no meio de uma edição. O nó preso recebe `cycleValue`, e quem depende dele
 * também.
 */
export function induct(
  edges: Map<string, string[]>,
  {
    combine,
    cycleValue,
  }: { combine: (neighbours: number[]) => number; cycleValue: number }
): Record<string, number> {
  const value: Record<string, number> = {};
  const onPath = new Set<string>();

  for (const start of edges.keys()) {
    if (value[start] !== undefined) continue;
    const stack: [string, boolean][] = [[start, false]];
    while (stack.length > 0) {
      const [name, expanded] = stack.pop()!;
      if (expanded) {
        onPath.delete(name);
        // Vizinho apontando para disciplina inexistente é ignorado: é o
        // estado de uma renomeação a meio.
        const neighbours = (edges.get(name) ?? []).filter((n) => edges.has(n));
        value[name] = neighbours.some((n) => value[n] === cycleValue)
          ? cycleValue
          : combine(neighbours.map((n) => value[n]));
        continue;
      }
      if (value[name] !== undefined) continue;
      if (onPath.has(name)) {
        value[name] = cycleValue;
        continue;
      }
      onPath.add(name);
      stack.push([name, true]);
      for (const neighbour of edges.get(name) ?? []) {
        if (edges.has(neighbour)) stack.push([neighbour, false]);
      }
    }
  }
  return value;
}
