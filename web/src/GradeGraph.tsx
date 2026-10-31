import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import { CYCLIC, curriculumPeriods } from "./curriculum";
import type { DisciplineInput } from "./types";

/** Um conector entre duas disciplinas, já em coordenadas do contêiner. O traço
 * é uma cúbica de tangentes horizontais, e não leva ponta: a cadeia corre da
 * esquerda para a direita, então o sentido está na própria posição das
 * colunas. */
interface Arrow {
  key: string;
  from: string;
  to: string;
  d: string;
}

const formatHours = (hours: number) => hours.toLocaleString("pt-BR");

/** Dificuldade e atratividade do cartão. As duas se leem em **múltiplos da
 * disciplina média**, então 1 é o neutro e é o que não merece destaque: o que
 * a vista precisa achar numa grade de dezenas de cartões é quem foge dele.
 * Daí o peso only acima de 1 e o recuo abaixo — a escala é a mesma, a ênfase é
 * que é assimétrica. */
const trait = (value: number | undefined) => {
  const amount = value ?? 1;
  const level = amount > 1 ? "is-high" : amount < 1 ? "is-low" : undefined;
  return (
    <span className={level}>{amount.toLocaleString("pt-BR")}</span>
  );
};

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
   * pré-requisito de ninguém, então não há cadeia que ordene o catálogo. Quem
   * ordena no lugar dele é a **oferta**: uma coluna por patamar de vagas, da
   * mais abundante para a mais apertada.
   *
   * É o mesmo gesto das obrigatórias, e de propósito. Ali as colunas correm da
   * entrada larga à ponta estreita do funil; aqui correm do patamar farto ao
   * escasso. Nos dois blocos, andar para a direita é andar para a disputa — e
   * como vagas é justamente o eixo que o obrigatório não consegue medir (lá
   * ele está confundido com o período), é no bloco das optativas que ele
   * precisa estar legível. */
  const electiveColumns = useMemo(() => {
    const bySeats = new Map<number, DisciplineInput[]>();
    for (const discipline of electives) {
      const group = bySeats.get(discipline.seats);
      if (group) group.push(discipline);
      else bySeats.set(discipline.seats, [discipline]);
    }
    return [...bySeats.entries()]
      .sort(([a], [b]) => b - a)
      .map(([seats, cards]) => ({ seats, cards }));
  }, [electives]);

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

  /** Os dois lados da cadeia saem no **mesmo** tom: o que separa "exige" de
   * "destrava" é a coluna em que o cartão está, e a grade corre num sentido
   * só. */
  const cardClass = (name: string) => {
    if (!hover) return "grade-card";
    if (hover === name) return "grade-card is-focus";
    return related(name) ? "grade-card is-chain" : "grade-card is-mute";
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
        // Metade do vão em cada ponta, e nada além dele: com a tangente mais
        // longa que a distância, as duas pontas se ultrapassam e a curva estufa
        // num S. O teto segura as que saltam colunas.
        const pull = Math.max(8, Math.min(Math.abs(x2 - x1) / 2, 48));
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
      <p className="grade-traits">
        dif. {trait(discipline.difficulty)} · atr. {trait(discipline.attractiveness)}
      </p>
    </article>
  );

  return (
    <div>
      <h1>Grade</h1>

      <div className="grade-scroll">
        <div className="grade-sheet" ref={containerRef}>
          <svg className="grade-arrows" aria-hidden="true">
            {arrows.map((arrow) => (
              <path
                key={arrow.key}
                className={
                  hover ? (related(arrow.from) && related(arrow.to) ? "is-lit" : "is-dim") : ""
                }
                d={arrow.d}
              />
            ))}
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
              <div className="grade-columns">
                {electiveColumns.map((column) => (
                  <div className="grade-column" key={column.seats}>
                    <div className="grade-column-head">{column.seats} vagas</div>
                    {column.cards.map(card)}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
