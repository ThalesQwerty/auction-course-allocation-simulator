/** Indução sobre a DAG de pré-requisitos, iterativa */
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
