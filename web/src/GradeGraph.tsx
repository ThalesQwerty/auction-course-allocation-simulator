import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { CYCLIC, curriculumPeriods } from "./curriculum";
import type { DisciplineInput } from "./types";

/** Uma seta entre duas disciplinas, já em coordenadas do contêiner. O traço é
 * uma cúbica de tangentes horizontais: a cadeia corre da esquerda para a
 * direita, e a curva dá o sentido sem depender só da ponta. */
interface Arrow {
  key: string;
  from: string;
  to: string;
  d: string;
}

const formatHours = (hours: number) => hours.toLocaleString("pt-BR");

const totalHours = (list: DisciplineInput[]) =>
  list.reduce((sum, discipline) => sum + discipline.hours, 0);

export function GradeGraph({ disciplines }: { disciplines: DisciplineInput[] }) {
  const periods = useMemo(() => curriculumPeriods(disciplines), [disciplines]);
  const required = useMemo(() => disciplines.filter((d) => !d.elective), [disciplines]);
  const electives = useMemo(() => disciplines.filter((d) => d.elective), [disciplines]);

  /** As colunas das obrigatórias — uma por período da grade, na ordem. O
   * período não se configura: sai da indução sobre os pré-requisitos
   * (`curriculum.ts`). A última coluna recolhe o que está preso num ciclo, que
   * é período nenhum mas é o estado normal do formulário no meio de uma edição. */
  const columns = useMemo(() => {
    const placed = required.filter((d) => periods[d.name] >= 1);
    const last = placed.reduce((max, d) => Math.max(max, periods[d.name]), 0);
    const result: { period: number; cards: DisciplineInput[] }[] = [];
    for (let period = 1; period <= last; period++) {
      const cards = placed.filter((d) => periods[d.name] === period);
      if (cards.length) result.push({ period, cards });
    }
    const broken = required.filter((d) => periods[d.name] < 1);
    if (broken.length) result.push({ period: CYCLIC, cards: broken });
    return result;
  }, [required, periods]);

  /** A optativa não tem período a mostrar: não destrava nada e não é
   * pré-requisito de ninguém, então não há cadeia que ordene o catálogo. Sem
   * eixo, o bloco tende ao **quadrado** — tantas colunas quanto a raiz do
   * número de disciplinas, e as linhas que daí saírem. */
  const electiveColumns = Math.max(1, Math.ceil(Math.sqrt(electives.length)));

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

  /** Com o mouse sobre uma disciplina, a cadeia dela se acende e o resto recua:
   * numa grade de dezenas de cartões é o apagar do que não é da cadeia que faz
   * o caminho aparecer. */
  const related = useCallback(
    (name: string) =>
      hover !== null &&
      (name === hover ||
        (links.prereq.get(hover)?.has(name) ?? false) ||
        (links.postreq.get(hover)?.has(name) ?? false)),
    [hover, links]
  );

  const cardClass = (name: string) => {
    if (!hover) return "grade-card";
    if (hover === name) return "grade-card is-focus";
    if (links.prereq.get(hover)?.has(name)) return "grade-card is-prereq";
    if (links.postreq.get(hover)?.has(name)) return "grade-card is-postreq";
    return "grade-card is-mute";
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
        // Sai pela direita de quem destrava e chega pela esquerda de quem é
        // destravada: a grade corre na horizontal, então é esse o par de bordas
        // que não atravessa o próprio cartão.
        const x1 = start.right - origin.left;
        const y1 = start.top + start.height / 2 - origin.top;
        const x2 = end.left - origin.left;
        const y2 = end.top + end.height / 2 - origin.top;
        const pull = Math.max(24, Math.abs(x2 - x1) / 2);
        next.push({
          key: `${discipline.name}->${successor}`,
          from: discipline.name,
          to: successor,
          d: `M ${x1} ${y1} C ${x1 + pull} ${y1}, ${x2 - pull} ${y2}, ${x2} ${y2}`,
        });
      }
    }
    setArrows((current) =>
      current.length === next.length &&
      current.every((arrow, index) => arrow.key === next[index].key && arrow.d === next[index].d)
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

  const card = (discipline: DisciplineInput) => (
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
      <h3>{discipline.name}</h3>
      <p>
        {discipline.seats} vagas · {discipline.hours} h
        {discipline.entry && <em>entrada</em>}
      </p>
    </article>
  );

  return (
    <div>
      <h1>Grade</h1>
      <p className="note">
        São duas grades porque são duas regras de conclusão. Nas{" "}
        <strong>obrigatórias</strong> cada coluna é um período da grade, lido da esquerda para a
        direita; o período não se configura, sai da indução sobre os pré-requisitos. As{" "}
        <strong>optativas</strong> não têm período — o aluno escolhe quais cursar até somar a carga
        exigida, e é essa substituibilidade que as põe num bloco sem ordem. Com o mouse sobre uma
        disciplina, o que ela exige fica <span className="grade-key up">azul</span> e o que ela
        destrava fica <span className="grade-key down">barro</span>.
      </p>

      <div className="grade-scroll">
        <div className="grade-sheet" ref={containerRef}>
          <svg className="grade-arrows" aria-hidden="true">
            <defs>
              <marker id="grade-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                <path className="arrow-head" d="M0,0 L6,3 L0,6" />
              </marker>
              <marker
                id="grade-arrow-lit"
                markerWidth="8"
                markerHeight="8"
                refX="6"
                refY="3"
                orient="auto"
              >
                <path className="arrow-head is-lit" d="M0,0 L6,3 L0,6" />
              </marker>
            </defs>
            {arrows.map((arrow) => {
              const lit = related(arrow.from) && related(arrow.to);
              return (
                <path
                  key={arrow.key}
                  className={hover ? (lit ? "is-lit" : "is-dim") : ""}
                  d={arrow.d}
                  markerEnd={lit ? "url(#grade-arrow-lit)" : "url(#grade-arrow)"}
                />
              );
            })}
          </svg>

          {columns.length > 0 && (
            <section className="grade-block">
              <header className="grade-block-head">
                <h2>Obrigatórias</h2>
                <p>
                  {required.length} disciplinas · {formatHours(totalHours(required))} h · conclui
                  quem aprova em todas
                </p>
              </header>
              <div className="grade-columns">
                {columns.map((column) => (
                  <div className="grade-column" key={column.period}>
                    <div className="grade-column-head">
                      {column.period === CYCLIC ? "ciclo" : `${column.period}º`}
                    </div>
                    {column.cards.map(card)}
                  </div>
                ))}
              </div>
            </section>
          )}

          {electives.length > 0 && (
            <section className="grade-block">
              <header className="grade-block-head">
                <h2>Optativas</h2>
                <p>
                  {electives.length} disciplinas · {formatHours(totalHours(electives))} h ofertadas
                  · sem pré-requisito e sem período
                </p>
              </header>
              <div
                className="grade-square"
                style={{ "--grade-cols": electiveColumns } as CSSProperties}
              >
                {electives.map(card)}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
