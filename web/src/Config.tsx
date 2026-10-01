import { useMemo, useState } from "react";
import { PresetList } from "./PresetList";
import { CREDIT_RETURN_POLICIES } from "./types";
import type { CourseInput, CreditReturnPolicy, DisciplineInput, SimulateRequest } from "./types";

type Classification = "required" | "elective" | "free";

function classify(course: CourseInput, discipline: string): Classification {
  if (course.required.includes(discipline)) return "required";
  if (course.electives.includes(discipline)) return "elective";
  return "free";
}

/** Clique no chip alterna livre -> obrigatória -> optativa -> livre. */
function cycle(course: CourseInput, discipline: string): CourseInput {
  const required = course.required.filter((name) => name !== discipline);
  const electives = course.electives.filter((name) => name !== discipline);
  switch (classify(course, discipline)) {
    case "free":
      return { ...course, required: [...required, discipline], electives };
    case "required":
      return { ...course, required, electives: [...electives, discipline] };
    default:
      return { ...course, required, electives };
  }
}

export function Config({
  config,
  setConfig,
  running,
  error,
  onRun,
  presetId,
  hasCustom,
  onSelectPreset,
}: {
  config: SimulateRequest;
  setConfig: (update: (current: SimulateRequest) => SimulateRequest) => void;
  running: boolean;
  error: string | null;
  onRun: () => void;
  presetId: string | null;
  hasCustom: boolean;
  onSelectPreset: (presetId: string | null) => void;
}) {
  const hoursByDiscipline = useMemo(
    () => Object.fromEntries(config.disciplines.map((d) => [d.name, d.hours])),
    [config.disciplines]
  );

  // O input de escassez esperada escreve nas vagas, e as vagas escrevem nele de
  // volta. Enquanto o usuario digita, o rascunho segura o texto cru: sem ele um
  // "1." viraria 1 na hora, reescalaria as vagas e apagaria o que ele ia digitar.
  const [scarcityDraft, setScarcityDraft] = useState<string | null>(null);

  function patch(values: Partial<SimulateRequest>) {
    setConfig((current) => ({ ...current, ...values }));
  }
  function updateDiscipline(index: number, values: Partial<DisciplineInput>) {
    setConfig((current) => ({
      ...current,
      disciplines: current.disciplines.map((d, i) => (i === index ? { ...d, ...values } : d)),
    }));
  }
  function updateCourse(index: number, values: Partial<CourseInput>) {
    setConfig((current) => ({
      ...current,
      courses: current.courses.map((c, i) => (i === index ? { ...c, ...values } : c)),
    }));
  }

  // Uma geração por período *com ingresso*: a população é esse número vezes L,
  // não vezes |T|. Depois do L-ésimo período ninguém mais entra — os períodos
  // de drenagem não têm geração correspondente.
  const entrySpan = Math.min(config.entry_periods ?? config.periods, config.periods);
  const drainPeriods = config.periods - entrySpan;
  const studentsPerGeneration = config.courses.reduce(
    (sum, c) => sum + c.students_per_generation,
    0
  );
  const totalStudents = studentsPerGeneration * entrySpan;
  const totalSeats = config.disciplines.reduce((sum, d) => sum + d.seats, 0);

  // Piso de períodos para concluir o curso mais longo: nem quem nunca reprova
  // nem perde uma vaga fecha S_k em menos de ceil(S_k / W_a). Um prazo de
  // jubilamento abaixo disso desliga a população inteira por construção.
  const floorPeriods = config.courses.reduce(
    (worst, c) => Math.max(worst, Math.ceil(c.hours_to_graduate / Math.max(config.max_hours, 1))),
    0
  );
  // 0 desliga o jubilamento, então não há prazo curto demais a avisar.
  const deadlineTooTight = config.max_residence > 0 && config.max_residence < floorPeriods;
  // Com prazo, |T| = L - 1 + T_max observa toda geração até ela sair: no fim do
  // horizonte ninguém ficou em aberto, e as gerações viram comparáveis entre si.
  const closingHorizon =
    config.max_residence > 0 ? entrySpan - 1 + config.max_residence : null;

  // Escassez esperada: o tamanho de uma geração dividido pelas vagas ofertadas.
  // Não é a escassez dos resultados (Σ 1/vagas elegíveis, aluno a aluno) — esta
  // é uma razão global do cenário, para dimensionar a oferta antes de rodar.
  // Dimensiona pelo *fluxo* de entrada, não pela população ativa: quantas
  // gerações disputam ao mesmo tempo depende de quanto cada uma demora a sair,
  // que é resultado da simulação e não dá para saber antes de rodar.
  const expectedScarcity = totalSeats > 0 ? studentsPerGeneration / totalSeats : null;
  const scarcityDisplay = expectedScarcity === null ? "" : expectedScarcity.toFixed(2);
  // Sem aluno não há alvo a perseguir; sem vaga não há de que partir.
  const scalable = totalSeats > 0 && studentsPerGeneration > 0;

  /** Reescala as vagas de todas as disciplinas por um mesmo multiplicador para
   * que a escassez esperada caia em `raw`. Vaga é inteira, então o
   * arredondamento faz o valor obtido flutuar um pouco em torno do pedido. */
  function applyScarcity(raw: string) {
    const target = Number(raw);
    setScarcityDraft(null);
    // Mesmo texto que já estava lá (um foco sem edição) não mexe nas vagas.
    if (raw === scarcityDisplay) return;
    if (!scalable || !Number.isFinite(target) || target <= 0) return;
    const multiplier = studentsPerGeneration / target / totalSeats;
    setConfig((current) => ({
      ...current,
      disciplines: current.disciplines.map((d) =>
        // Disciplina sem vaga fica sem vaga, e nenhuma com vaga chega a zero:
        // arredondar para baixo até zerar mandaria a escassez para o infinito.
        d.seats > 0 ? { ...d, seats: Math.max(1, Math.round(d.seats * multiplier)) } : d
      ),
    }));
  }

  return (
    <div className="rail-layout">
      <div className="rail-layout-main">
      <h1>Configurar simulação</h1>

      {error && <div className="error-banner">{error}</div>}

      <div className="panel">
        <h2>Configurações gerais</h2>
        <div className="field-row">
          <div className="field">
            <label>Períodos (|T|)</label>
            <input type="number" min={1} max={40} value={config.periods} onChange={(e) => patch({ periods: Number(e.target.value) })} />
            <span className="field-hint">
              {drainPeriods > 0
                ? `${entrySpan} com ingresso + ${drainPeriods} de drenagem, em que ninguém entra e a população só diminui`
                : entrySpan === 1
                  ? "todos entram no primeiro período"
                  : `ingresso em todos: ${entrySpan} gerações, uma por período`}
            </span>
          </div>
          <div className="field">
            <label>Períodos com ingresso (L)</label>
            <input
              type="number"
              min={1}
              max={config.periods}
              placeholder={String(config.periods)}
              value={config.entry_periods ?? ""}
              onChange={(e) =>
                patch({ entry_periods: e.target.value === "" ? null : Number(e.target.value) })
              }
            />
            <span className="field-hint">
              Vazio = ingresso em todos os |T|. Só existem L gerações: os períodos
              seguintes não têm geração correspondente, eles drenam os que já
              entraram. Sem drenagem as últimas gerações são cortadas pelo
              horizonte antes de poderem se formar.
            </span>
          </div>
          <div className="field">
            <label>Tempo máximo de permanência (T<sub>max</sub>)</label>
            <input
              type="number"
              min={0}
              max={config.periods}
              className={deadlineTooTight ? "invalid" : undefined}
              value={config.max_residence}
              onChange={(e) => patch({ max_residence: Number(e.target.value) })}
            />
            <span className="field-hint">
              Jubilamento: quem completa T<sub>max</sub> períodos sem concluir é
              desligado e sai da disputa. <strong>0 desliga a regra</strong> — o
              jubilamento é opcional.{" "}
              {deadlineTooTight ? (
                <span className="invalid-text">
                  Abaixo do piso de {floorPeriods} períodos (⌈S<sub>k</sub> ÷ W<sub>a</sub>⌉ do
                  curso mais longo): ninguém conseguiria concluir a tempo.
                </span>
              ) : closingHorizon !== null ? (
                <>
                  Piso teórico: {floorPeriods} períodos. Com |T| = {closingHorizon} toda geração
                  sai por uma das duas portas antes do fim — nenhuma fica em aberto.
                </>
              ) : (
                <>Piso teórico: {floorPeriods} períodos.</>
              )}
            </span>
          </div>
          <div className="field">
            <label>Rodadas por período (|R|)</label>
            <input type="number" min={1} max={10} value={config.rounds} onChange={(e) => patch({ rounds: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label>Nota mínima (n<sub>min</sub>)</label>
            <input type="number" min={0.1} max={10} step={0.1} value={config.min_grade} onChange={(e) => patch({ min_grade: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label>Créditos base por período (Γ<sub>min</sub>)</label>
            <input type="number" min={1} value={config.base_credits} onChange={(e) => patch({ base_credits: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label>Carga horária máxima por período (W<sub>a</sub>)</label>
            <input type="number" min={1} value={config.max_hours} onChange={(e) => patch({ max_hours: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label>Incremento de aprendizado (pontos por recursada)</label>
            <input type="number" min={0.1} max={10} step={0.1} value={config.learning_gain} onChange={(e) => patch({ learning_gain: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label>Retorno de créditos (f<sub>γ</sub>)</label>
            <select
              value={config.credit_return}
              onChange={(e) => patch({ credit_return: e.target.value as CreditReturnPolicy })}
            >
              {CREDIT_RETURN_POLICIES.map((policy) => (
                <option key={policy.value} value={policy.value}>
                  {policy.label}
                </option>
              ))}
            </select>
            <span className="field-hint">
              {CREDIT_RETURN_POLICIES.find((p) => p.value === config.credit_return)?.hint}
            </span>
          </div>
          <div className="field">
            <label>Seed</label>
            <input type="number" value={config.seed} onChange={(e) => patch({ seed: Number(e.target.value) })} />
          </div>
        </div>
        <p className="note">
          Alunos, nomes, utilidades e notas são sorteados a partir da seed. A mesma configuração sempre
          produz a mesma simulação.
        </p>
      </div>

      <div className="panel">
        <h2>Disciplinas — {config.disciplines.length} ofertadas, {totalSeats} vagas</h2>
        <div className="field-row">
          <div className="field">
            <label>Escassez esperada</label>
            <input
              type="number"
              min={0.01}
              step={0.1}
              disabled={!scalable}
              value={scarcityDraft ?? scarcityDisplay}
              onChange={(e) => setScarcityDraft(e.target.value)}
              onBlur={(e) => applyScarcity(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") e.currentTarget.blur();
              }}
            />
            <span className="field-hint">
              {scalable ? (
                <>
                  {studentsPerGeneration} ingressantes por período ÷ {totalSeats} vagas. Alterar reescala as
                  vagas de todas as disciplinas pelo mesmo multiplicador; como vaga é inteira, o
                  arredondamento devolve um valor próximo do pedido, não exato.
                </>
              ) : (
                "cadastre cursos com alunos e disciplinas com vagas para dimensionar a oferta"
              )}
            </span>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th style={{ width: 110 }}>Vagas</th>
              <th style={{ width: 140 }}>Carga horária</th>
              <th style={{ width: 90 }} />
            </tr>
          </thead>
          <tbody>
            {config.disciplines.map((discipline, i) => (
              <tr key={i}>
                <td><input value={discipline.name} onChange={(e) => updateDiscipline(i, { name: e.target.value })} /></td>
                <td><input type="number" min={0} value={discipline.seats} onChange={(e) => updateDiscipline(i, { seats: Number(e.target.value) })} /></td>
                <td><input type="number" min={1} value={discipline.hours} onChange={(e) => updateDiscipline(i, { hours: Number(e.target.value) })} /></td>
                <td>
                  <button
                    className="danger"
                    onClick={() =>
                      setConfig((current) => {
                        const removed = current.disciplines[i].name;
                        return {
                          ...current,
                          disciplines: current.disciplines.filter((_, j) => j !== i),
                          courses: current.courses.map((c) => ({
                            ...c,
                            required: c.required.filter((name) => name !== removed),
                            electives: c.electives.filter((name) => name !== removed),
                          })),
                        };
                      })
                    }
                  >
                    remover
                  </button>
                </td>
              </tr>
            ))}
            {config.disciplines.length === 0 && (
              <tr><td colSpan={4} className="empty-state">Nenhuma disciplina ainda.</td></tr>
            )}
          </tbody>
        </table>
        <div className="actions">
          <button
            className="secondary"
            onClick={() =>
              setConfig((current) => ({
                ...current,
                disciplines: [
                  ...current.disciplines,
                  { name: `Disciplina ${current.disciplines.length + 1}`, seats: 20, hours: 60 },
                ],
              }))
            }
          >
            + adicionar disciplina
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>Cursos — {config.courses.length} cursos, {totalStudents} alunos</h2>
        {config.courses.map((course, i) => {
          const requiredHours = course.required.reduce((sum, name) => sum + (hoursByDiscipline[name] ?? 0), 0);
          const electiveHours = course.electives.reduce((sum, name) => sum + (hoursByDiscipline[name] ?? 0), 0);
          const valid =
            course.hours_to_graduate >= requiredHours &&
            course.hours_to_graduate <= requiredHours + electiveHours;
          return (
            <div className="subpanel" key={i}>
              <div className="field-row">
                <div className="field grow">
                  <label>Nome do curso</label>
                  <input value={course.name} onChange={(e) => updateCourse(i, { name: e.target.value })} />
                </div>
                <div className="field">
                  <label>Alunos por geração</label>
                  <input
                    type="number"
                    min={0}
                    value={course.students_per_generation}
                    onChange={(e) => updateCourse(i, { students_per_generation: Number(e.target.value) })}
                  />
                  <span className="field-hint">
                    {course.students_per_generation * entrySpan} alunos no curso, em {entrySpan}{" "}
                    {entrySpan === 1 ? "geração" : "gerações"}
                  </span>
                </div>
                <div className="field">
                  <label>Horas para conclusão (S<sub>k</sub>)</label>
                  <input
                    type="number"
                    min={0}
                    step={10}
                    className={valid ? undefined : "invalid"}
                    value={course.hours_to_graduate}
                    onChange={(e) => updateCourse(i, { hours_to_graduate: Number(e.target.value) })}
                  />
                </div>
                <button className="danger" onClick={() => setConfig((c) => ({ ...c, courses: c.courses.filter((_, j) => j !== i) }))}>
                  remover curso
                </button>
              </div>

              <p className="note">
                Grade curricular — clique para alternar entre livre, obrigatória e optativa.
                Obrigatórias: {requiredHours} h · optativas: {electiveHours} h ·{" "}
                <span className={valid ? undefined : "invalid-text"}>
                  conclusão deve ficar entre {requiredHours} h e {requiredHours + electiveHours} h
                </span>
              </p>
              <div className="chips">
                {config.disciplines.map((discipline) => {
                  const kind = classify(course, discipline.name);
                  return (
                    <button
                      key={discipline.name}
                      className={`chip ${kind}`}
                      onClick={() => updateCourse(i, cycle(course, discipline.name))}
                    >
                      {discipline.name}
                    </button>
                  );
                })}
                {config.disciplines.length === 0 && <span className="empty-state">Cadastre disciplinas primeiro.</span>}
              </div>
            </div>
          );
        })}
        <div className="actions">
          <button
            className="secondary"
            onClick={() =>
              setConfig((current) => ({
                ...current,
                courses: [
                  ...current.courses,
                  { name: `Curso ${current.courses.length + 1}`, students_per_generation: 3, hours_to_graduate: 0, required: [], electives: [] },
                ],
              }))
            }
          >
            + adicionar curso
          </button>
        </div>
      </div>

      <div className="actions sticky-actions">
        <button className="primary" disabled={running} onClick={onRun}>
          {running ? "Simulando..." : "Executar simulação"}
        </button>
      </div>
      </div>

      <PresetList selected={presetId} hasCustom={hasCustom} onSelect={onSelectPreset} />
    </div>
  );
}
