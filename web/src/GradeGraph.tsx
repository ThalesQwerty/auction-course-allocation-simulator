import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { curriculumPeriods } from "./curriculum";
import type { DisciplineInput } from "./types";

interface Arrow {
  key: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export function GradeGraph({ disciplines }: { disciplines: DisciplineInput[] }) {
  const periods = useMemo(() => curriculumPeriods(disciplines), [disciplines]);
  const rows = useMemo(() => {
    const placed = disciplines.filter((d) => periods[d.name] >= 1);
    const maxPeriod = placed.reduce((max, d) => Math.max(max, periods[d.name]), 0);
    const levels = [];
    for (let period = 1; period <= maxPeriod; period++) {
      const row = placed.filter((d) => periods[d.name] === period);
      if (row.length) levels.push(row);
    }
    const broken = disciplines.filter((d) => periods[d.name] < 1);
    if (broken.length) levels.push(broken);
    return levels;
  }, [disciplines, periods]);

  const links = useMemo(() => {
    const incoming = new Map<string, string[]>();
    const outgoing = new Map<string, string[]>();
    for (const discipline of disciplines) {
      incoming.set(discipline.name, []);
      outgoing.set(discipline.name, discipline.unlocks.filter((name) => name !== discipline.name));
    }
    for (const discipline of disciplines) {
      for (const successor of outgoing.get(discipline.name) ?? []) {
        incoming.get(successor)?.push(discipline.name);
      }
    }
    const reachable = (start: string, steps: Map<string, string[]>) => {
      const seen = new Set<string>();
      const stack = [...(steps.get(start) ?? [])];
      while (stack.length > 0) {
        const name = stack.pop()!;
        if (name === start || seen.has(name)) continue;
        seen.add(name);
        for (const next of steps.get(name) ?? []) stack.push(next);
      }
      return seen;
    };
    const prereq = new Map<string, Set<string>>();
    const postreq = new Map<string, Set<string>>();
    for (const discipline of disciplines) {
      prereq.set(discipline.name, reachable(discipline.name, incoming));
      postreq.set(discipline.name, reachable(discipline.name, outgoing));
    }
    return { prereq, postreq };
  }, [disciplines]);

  const [hover, setHover] = useState<string | null>(null);
  const cardClass = (name: string) => {
    if (hover === name) return "grade-card is-focus";
    if (hover && links.prereq.get(hover)?.has(name)) return "grade-card is-prereq";
    if (hover && links.postreq.get(hover)?.has(name)) return "grade-card is-postreq";
    return "grade-card";
  };

  const containerRef = useRef<HTMLDivElement>(null);
  const cards = useRef(new Map<string, HTMLElement>());
  const [arrows, setArrows] = useState<Arrow[]>([]);

  const measure = useCallback(() => {
    const root = containerRef.current;
    if (!root) return;
    const origin = root.getBoundingClientRect();
    const next: Arrow[] = [];
    for (const discipline of disciplines) {
      const from = cards.current.get(discipline.name);
      if (!from) continue;
      const start = from.getBoundingClientRect();
      for (const successor of discipline.unlocks) {
        const to = cards.current.get(successor);
        if (!to) continue;
        const end = to.getBoundingClientRect();
        next.push({
          key: `${discipline.name}->${successor}`,
          x1: start.left + start.width / 2 - origin.left,
          y1: start.bottom - origin.top,
          x2: end.left + end.width / 2 - origin.left,
          y2: end.top - origin.top,
        });
      }
    }
    setArrows((current) =>
      current.length === next.length &&
      current.every(
        (arrow, index) =>
          arrow.key === next[index].key &&
          arrow.x1 === next[index].x1 &&
          arrow.y1 === next[index].y1 &&
          arrow.x2 === next[index].x2 &&
          arrow.y2 === next[index].y2
      )
        ? current
        : next
    );
  }, [disciplines]);

  useLayoutEffect(() => {
    measure();
    const root = containerRef.current;
    if (!root) return;
    const observer = new ResizeObserver(measure);
    observer.observe(root);
    return () => observer.disconnect();
  }, [measure]);

  return (
    <div>
      <h1>Grade</h1>
      <div className="grade-graph" ref={containerRef}>
        <svg className="grade-arrows" aria-hidden="true">
          <defs>
            <marker id="grade-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L6,3 L0,6" fill="none" stroke="currentColor" />
            </marker>
          </defs>
          {arrows.map((arrow) => (
            <line
              key={arrow.key}
              x1={arrow.x1}
              y1={arrow.y1}
              x2={arrow.x2}
              y2={arrow.y2}
              markerEnd="url(#grade-arrow)"
            />
          ))}
        </svg>
        {rows.map((row) => (
          <div className="grade-row" key={periods[row[0].name]}>
            {row.map((discipline) => {
              const offer = discipline;
              return (
                <article
                  key={discipline.name}
                  className={cardClass(discipline.name)}
                  onMouseEnter={() => setHover(discipline.name)}
                  onMouseLeave={() => setHover(null)}
                  ref={(node) => {
                    if (node) cards.current.set(discipline.name, node);
                    else cards.current.delete(discipline.name);
                  }}
                >
                  <h2>{discipline.name}</h2>
                  <p>
                    {offer.seats} vagas · {offer.hours} h
                    {discipline.entry && <em>entrada</em>}
                  </p>
                </article>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
