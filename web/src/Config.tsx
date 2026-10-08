import { useMemo, useState } from "react";
import { CYCLIC, curriculumLength, curriculumPeriods } from "./curriculum";
import { PresetList } from "./PresetList";
import {
  CREDIT_RETURN_POLICIES,
  COMPARISON_ARMS,
  DEFAULT_SWEEP,
  MAX_COMPARISON_RUNS,
} from "./types";
import type {
  CreditReturnPolicy,
  DisciplineInput,
  SimulateRequest,
  SweepIn,
} from "./types";

/** O que o botão executa. O **cenário é o mesmo nos dois**: o que muda é se
 * ele roda uma vez, com a seed do formulário, ou N vezes de cada lado dos dois
 * mecanismos, com as seeds de 1 a N. Por isso o modo não vive dentro do
 * cenário — trocar de modo não pode mexer no que está configurado. */
export type RunMode = "single" | "compare";

/** Nome livre para uma disciplina nova, sem colidir com as que já existem —
 * nome repetido é rejeitado pelo motor, e o usuário levaria o erro só ao rodar. */
function freshName(disciplines: DisciplineInput[]): string {
  const taken = new Set(disciplines.map((d) => d.name));
  for (let i = disciplines.length + 1; ; i++) {
    const candidate = `Disciplina ${i}`;
    if (!taken.has(candidate)) return candidate;
  }
}

export function Config({
  config,
  setConfig,
  mode,
  setMode,
  runs,
  setRuns,
  sweep,
  setSweep,
  running,
  error,
  onRun,
  presetId,
  hasCustom,
  onSelectPreset,
}: {
  config: SimulateRequest;
  setConfig: (update: (current: SimulateRequest) => SimulateRequest) => void;
  mode: RunMode;
  setMode: (mode: RunMode) => void;
  runs: number;
  setRuns: (runs: number) => void;
  /** `null` = só o k canônico. A varredura é o segundo eixo do experimento, e
   * custa pontos x 3 modelos x execuções simulações. */
  sweep: SweepIn | null;
  setSweep: (sweep: SweepIn | null) => void;
  running: boolean;
  error: string | null;
  onRun: () => void;
  presetId: string | null;
  hasCustom: boolean;
  onSelectPreset: (presetId: string | null) => void;
}) {
  const comparing = mode === "compare";
  // Qual disciplina está com o editor de pré-requisitos aberto. Uma de cada
  // vez: 36 grades de chips abertas ao mesmo tempo não se leem.
  const [editingPrerequisites, setEditingPrerequisites] = useState<string | null>(null);

  function patch(values: Partial<SimulateRequest>) {
    setConfig((current) => ({ ...current, ...values }));
  }

  function updateDiscipline(index: number, values: Partial<DisciplineInput>) {
    setConfig((current) => ({
      ...current,
      disciplines: current.disciplines.map((d, i) => (i === index ? { ...d, ...values } : d)),
    }));
  }

  /** Renomear arrasta as referências: quem tinha a disciplina como
   * pré-requisito continua tendo, senão a grade se desmontaria a cada letra. */
  function renameDiscipline(index: number, name: string) {
    setConfig((current) => {
      const previous = current.disciplines[index].name;
      return {
        ...current,
        disciplines: current.disciplines.map((d, i) => ({
          ...(i === index ? { ...d, name } : d),
          prerequisites: d.prerequisites.map((p) => (p === previous ? name : p)),
        })),
      };
    });
  }

  function togglePrerequisite(index: number, prerequisite: string) {
    setConfig((current) => ({
      ...current,
      disciplines: current.disciplines.map((d, i) =>
        i === index
          ? {
              ...d,
              prerequisites: d.prerequisites.includes(prerequisite)
                ? d.prerequisites.filter((p) => p !== prerequisite)
                : [...d.prerequisites, prerequisite],
            }
          : d
      ),
    }));
  }

  // Quantos pontos a varredura pediria, e quanto isso custa em simulações.
  const sweepPoints = sweep && sweep.max_sigma >= sweep.min_sigma ? sweep.points : 0;
  const sweepSimulations = sweepPoints * COMPARISON_ARMS.length * (sweep?.runs ?? 0);

  const periods = useMemo(() => curriculumPeriods(config.disciplines), [config.disciplines]);
  const hasCycle = Object.values(periods).some((p) => p === CYCLIC);
  const gradeLength = curriculumLength(config.disciplines);
  const firstPeriod = config.disciplines.filter((d) => periods[d.name] === 1);
  const entryHours = firstPeriod.reduce((sum, d) => sum + d.hours, 0);
  // O ingressante entra direto em todas as de 1º período: a geração tem de
  // caber na menor oferta delas, e a carga somada tem de caber em W_a (eq. 4).
  const smallestEntrySeats = firstPeriod.length
    ? Math.min(...firstPeriod.map((d) => d.seats))
    : 0;
  const entryTooLarge = config.students_per_period > smallestEntrySeats;
  const entryTooHeavy = entryHours > config.max_hours;

  // Uma geração por período *com ingresso*: a população é esse número vezes L,
  // não vezes |T|. Depois do L-ésimo período ninguém mais entra — os períodos
  // de drenagem não têm geração correspondente.
  const entrySpan = Math.min(config.entry_periods ?? config.periods, config.periods);
  const drainPeriods = config.periods - entrySpan;
  const totalStudents = config.students_per_period * entrySpan;
  const totalSeats = config.disciplines.reduce((sum, d) => sum + d.seats, 0);
  const totalHours = config.disciplines.reduce((sum, d) => sum + d.hours, 0);

  // Piso de períodos para concluir: nem quem nunca reprova nem perde uma vaga
  // fecha a grade antes disso. São dois limites e vale o maior — a carga
  // horária (⌈S ÷ W_a⌉) e a cadeia de pré-requisitos, que tem um elo por
  // período da grade. Um prazo de jubilamento abaixo disso desliga a população
  // inteira por construção.
  const floorPeriods = Math.max(
    Math.ceil(totalHours / Math.max(config.max_hours, 1)),
    gradeLength
  );

  return (
    <div className="rail-layout">
      <div className="rail-layout-main">
      <h1>Configurar {comparing ? "comparação" : "simulação"}</h1>

      {error && <div className="error-banner">{error}</div>}

      <div className="panel">
        <h2>Modo de execução</h2>
        <div className="field-row">
          <div className="field">
            <label>O que executar</label>
            <select value={mode} onChange={(e) => setMode(e.target.value as RunMode)}>
              <option value="single">uma simulação do leilão por créditos</option>
              <option value="compare">comparar os três modelos</option>
            </select>
          </div>
          {comparing && (
            <div className="field">
              <label>Execuções por mecanismo (N)</label>
              <input
                type="number"
                min={1}
                max={MAX_COMPARISON_RUNS}
                value={runs}
                onChange={(e) => setRuns(Number(e.target.value))}
              />
              <span className="field-hint">
                Seeds de 1 a {runs}, as mesmas nos três modelos —{" "}
                {runs * COMPARISON_ARMS.length} simulações no total. Com poucas seeds a dispersão
                da caixa mal se lê.
              </span>
            </div>
          )}
        </div>
        {comparing && (
          <div className="subpanel">
            <h3>
              Varredura da forma da preferência (<em>k</em>)
            </h3>
            <div className="field-row">
              <div className="field">
                <label>Varrer σ</label>
                <select
                  value={sweep ? "on" : "off"}
                  onChange={(e) => setSweep(e.target.value === "on" ? DEFAULT_SWEEP : null)}
                >
                  <option value="off">não — só o σ do cenário</option>
                  <option value="on">sim — uma faixa de σ</option>
                </select>
              </div>
              {sweep && (
                <>
                  <div className="field">
                    <label>σ mínimo</label>
                    <input
                      type="number"
                      min={0.01}
                      step={0.25}
                      value={sweep.min_sigma}
                      onChange={(e) => setSweep({ ...sweep, min_sigma: Number(e.target.value) })}
                    />
                  </div>
                  <div className="field">
                    <label>σ máximo</label>
                    <input
                      type="number"
                      min={0.01}
                      step={0.25}
                      value={sweep.max_sigma}
                      onChange={(e) => setSweep({ ...sweep, max_sigma: Number(e.target.value) })}
                    />
                  </div>
                  <div className="field">
                    <label>Pontos</label>
                    <input
                      type="number"
                      min={2}
                      max={41}
                      value={sweep.points}
                      onChange={(e) => setSweep({ ...sweep, points: Number(e.target.value) })}
                    />
                  </div>
                  <div className="field">
                    <label>Execuções por ponto</label>
                    <input
                      type="number"
                      min={1}
                      max={MAX_COMPARISON_RUNS}
                      value={sweep.runs}
                      onChange={(e) => setSweep({ ...sweep, runs: Number(e.target.value) })}
                    />
                  </div>
                </>
              )}
            </div>
            <p className="note">
              A varredura roda a comparação inteira em cada <em>σ</em> da faixa, em passos
              iguais. O <em>σ</em> do cenário ({config.utility_sigma.toLocaleString("pt-BR")}) é o{" "}
              <strong>canônico</strong> — o que os boxplots medem com N execuções —, e ele é
              marcado no eixo mesmo quando não cai exatamente num ponto varrido.{" "}
              {sweep ? (
                sweepPoints > 0 ? (
                  <>
                    São <strong>{sweepPoints} pontos</strong> de {sweep.runs} execuções ={" "}
                    <strong>{sweepSimulations} simulações</strong> a mais. Os gráficos de linha e
                    os histogramas de utilidade aparecem em seções próprias do resultado.
                  </>
                ) : (
                  <span className="invalid-text">
                    O σ mínimo não pode passar do máximo.
                  </span>
                )
              ) : (
                <>Desligada, o resultado traz só os boxplots.</>
              )}
            </p>
          </div>
        )}
        {comparing ? (
          <>
            <p className="note">
              O <strong>mesmo cenário</strong> roda nos dois mecanismos, e a seed pareia os dois
              lados: a i-ésima execução de um e a do outro partem da mesma população, das mesmas
              utilidades e das mesmas notas. É o que torna a diferença atribuível ao mecanismo, e
              não ao sorteio — a condição metodológica da Seção 7.3.
            </p>
            <ul className="note">
              {COMPARISON_ARMS.map((arm) => (
                <li key={arm.key}>
                  <strong>{arm.label}</strong> — {arm.hint}
                </li>
              ))}
            </ul>
            <p className="note">
              O leilão entra duas vezes porque o <strong>retorno de créditos</strong> é o eixo do
              experimento, não um parâmetro do cenário: é ele que pode devolver ao mecanismo algum
              senso meritocrático, e a única forma de ver quanto é rodar os dois sobre a mesma
              população. Por isso o campo de retorno some do formulário.
            </p>
            <p className="note">
              O resultado traz só as métricas de alocação, em boxplot: sem nada de crédito (não
              existe do lado da linha de base) e sem recorte por geração ou perfil.
            </p>
          </>
        ) : (
          <p className="note">
            Uma execução do mecanismo proposto, com todos os gráficos por período, os recortes por
            geração e perfil e a tela de depuração por aluno.
          </p>
        )}
      </div>

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
              horizonte antes de poderem se formar. Piso teórico para concluir:{" "}
              {floorPeriods} períodos — o maior entre ⌈{totalHours} h ÷ {config.max_hours} h⌉ e os{" "}
              {gradeLength} elos da cadeia de pré-requisitos.
            </span>
          </div>
          <div className="field">
            <label>Alunos novos por período</label>
            <input
              type="number"
              min={1}
              className={entryTooLarge ? "invalid" : undefined}
              value={config.students_per_period}
              onChange={(e) => patch({ students_per_period: Number(e.target.value) })}
            />
            <span className="field-hint">
              {totalStudents} alunos no total, em {entrySpan}{" "}
              {entrySpan === 1 ? "geração" : "gerações"}.{" "}
              {entryTooLarge ? (
                <span className="invalid-text">
                  Passa das {smallestEntrySeats} vagas da disciplina de 1º período mais
                  apertada: o ingressante tem vaga garantida em todas elas.
                </span>
              ) : (
                <>
                  Teto de {smallestEntrySeats} — a menor oferta entre as{" "}
                  {firstPeriod.length} disciplinas de 1º período, em que o ingressante
                  entra sem disputar. Sobram {smallestEntrySeats - config.students_per_period}{" "}
                  vagas ali para quem recursa.
                </>
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
          {/* Numa comparação o retorno não é parâmetro: é o eixo do
              experimento, e cada braço impõe o seu. Deixá-lo editável aqui
              daria a impressão de que mexer nele muda o resultado. */}
          {!comparing && (
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
          )}
          {!comparing && (
            <div className="field">
              <label>Seed</label>
              <input type="number" value={config.seed} onChange={(e) => patch({ seed: Number(e.target.value) })} />
            </div>
          )}
        </div>
        <p className="note">
          Alunos, nomes, utilidades e notas são sorteados a partir da seed. A mesma configuração sempre
          produz a mesma simulação.{" "}
          {comparing &&
            "Numa comparação a seed e o retorno de créditos deixam de ser parâmetros e viram eixos: as seeds são as de 1 a N, e o retorno é o que separa dois dos três modelos."}
        </p>
      </div>

      <div className="panel">
        <h2>Como são os alunos</h2>
        <p className="note">
          <strong>Não há perfis.</strong> Toda a população sai das duas normais abaixo, e o que
          distingue um aluno do outro é só o que a <em>seed</em> sorteou para ele — não há um
          grupo que erra mais que outro nem um que concentre mais a preferência. Os dois eixos de
          perfil existiram até 08/10/2026 e saíram; com eles saiu o recorte dos relatórios por
          perfil, e sobrou o recorte por geração.
        </p>

        <div className="subpanel">
          <h3>Notas — a normal de n⁰ e o que a recursada acrescenta</h3>
          <div className="field-row">
            <div className="field">
              <label>Média</label>
              <input
                type="number"
                min={0}
                max={10}
                step={0.1}
                value={config.grade_mean}
                onChange={(e) => patch({ grade_mean: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Desvio padrão</label>
              <input
                type="number"
                min={0.1}
                step={0.1}
                value={config.grade_stddev}
                onChange={(e) => patch({ grade_stddev: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Ganho por recursada</label>
              <input
                type="number"
                min={0.1}
                max={10}
                step={0.1}
                value={config.learning_gain}
                onChange={(e) => patch({ learning_gain: Number(e.target.value) })}
              />
            </div>
          </div>
          <p className="note">
            Cada par (aluno, disciplina) sorteia desta normal <strong>em cada período</strong>, e
            o resultado é truncado em [0, 10] e arredondado a 0,1. O desvio é o que dá dispersão de
            desempenho: sem ele o CR vira ruído e a correlação da eq. (57) não mede nada. O ganho é
            quanto a recursada desloca a <strong>média</strong> do sorteio (eq. 33) — quem repete
            tira uma nota nova, de uma normal mais alta, então a recursada não garante nota maior,
            mas a chance de aprovar sobe a cada tentativa e ninguém fica preso numa disciplina.
            A maior nota já obtida é a que conta para o CR.
          </p>
        </div>

        <div className="subpanel">
          <h3>Utilidades — o quanto o aluno diferencia as disciplinas</h3>
          <div className="field-row">
            <div className="field">
              <label>
                Desvio da log-normal (<em>σ</em>)
              </label>
              <input
                type="number"
                min={0.01}
                step={0.25}
                value={config.utility_sigma}
                onChange={(e) => patch({ utility_sigma: Number(e.target.value) })}
              />
            </div>
            <div className="field grow">
              <label>Carga horária máxima (W<sub>a</sub>)</label>
              <input
                type="number"
                min={1}
                step={30}
                className={entryTooHeavy ? "invalid" : undefined}
                value={config.max_hours}
                onChange={(e) => patch({ max_hours: Number(e.target.value) })}
              />
            </div>
          </div>
          <p className="note">
            Cada par (aluno, disciplina) sorteia um valor de uma <strong>log-normal</strong> de
            desvio <em>σ</em> <strong>em cada período</strong>, e a linha do aluno é dividida pelo
            somatório — então ela vale 1 sobre a grade inteira. O gosto dele é resorteado a cada
            semestre: o que quis no período passado não determina o que quer neste. Sobre a linha
            agem os zeros — a disciplina já aprovada ou ainda bloqueada por pré-requisito sai do
            conjunto elegível.
            <br />
            <em>σ</em> é o único controle (a média do logaritmo some na normalização), e{" "}
            <strong>grande concentra, pequeno achata</strong>. A faixa útil cabe entre ~0,25 (a
            preferida vale ~1,9× a menos querida, aluno quase indiferente) e ~3 (ele quer uma
            disciplina e despreza o resto). É o papel que o perfil de afinidade tinha.
          </p>
          <p className="note">
            {entryTooHeavy ? (
              <span className="invalid-text">
                As {firstPeriod.length} disciplinas de 1º período somam {entryHours} h e não cabem
                na carga horária máxima — o ingressante cursa todas de uma vez, e a eq. (4) tem de
                continuar valendo.
              </span>
            ) : (
              <>
                A carga máxima (W<sub>a</sub>) precisa comportar as {firstPeriod.length}{" "}
                disciplinas de 1º período, que somam {entryHours} h: é a matrícula garantida de
                quem ingressa.
              </>
            )}
          </p>
        </div>
      </div>

      <div className="panel">
        <h2>
          Grade — {config.disciplines.length} disciplinas, {gradeLength}{" "}
          {gradeLength === 1 ? "período" : "períodos"}, {totalSeats} vagas, {totalHours} h
        </h2>
        <p className="note">
          Toda disciplina é obrigatória: conclui o curso quem aprova em todas as{" "}
          {config.disciplines.length}. O <strong>período</strong> não é configurado — sai dos
          pré-requisitos: sem nenhum é 1º período, com pré-requisitos é o período seguinte ao
          mais tardio deles. As de 1º período são a matrícula garantida de quem ingressa, que
          entra nelas sem leilão.
        </p>
        {hasCycle && (
          <div className="error-banner">
            Há um ciclo de pré-requisitos: as disciplinas marcadas com <strong>ciclo</strong> não
            ficariam elegíveis em período nenhum. A simulação recusa o cenário enquanto ele
            existir.
          </div>
        )}

        <table>
          <thead>
            <tr>
              <th style={{ width: 80 }}>Período</th>
              <th>Nome</th>
              <th style={{ width: 90 }}>Vagas</th>
              <th style={{ width: 110 }}>Carga</th>
              <th>Pré-requisitos</th>
              <th style={{ width: 90 }} />
            </tr>
          </thead>
          <tbody>
            {config.disciplines.map((discipline, i) => {
              const period = periods[discipline.name];
              const open = editingPrerequisites === discipline.name;
              return (
                <tr key={i}>
                  <td className={period === CYCLIC ? "invalid-text" : "muted-cell"}>
                    {period === CYCLIC ? "ciclo" : `${period}º`}
                  </td>
                  <td>
                    <input
                      value={discipline.name}
                      onChange={(e) => renameDiscipline(i, e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min={0}
                      className={
                        period === 1 && discipline.seats < config.students_per_period
                          ? "invalid"
                          : undefined
                      }
                      value={discipline.seats}
                      onChange={(e) => updateDiscipline(i, { seats: Number(e.target.value) })}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min={1}
                      value={discipline.hours}
                      onChange={(e) => updateDiscipline(i, { hours: Number(e.target.value) })}
                    />
                  </td>
                  <td>
                    <button
                      className="link"
                      onClick={() => setEditingPrerequisites(open ? null : discipline.name)}
                    >
                      {discipline.prerequisites.length === 0
                        ? "nenhum (1º período)"
                        : discipline.prerequisites.join(", ")}
                    </button>
                    {open && (
                      <div className="chips">
                        {config.disciplines
                          .filter((other) => other.name !== discipline.name)
                          .map((other) => (
                            <button
                              key={other.name}
                              className={`chip ${
                                discipline.prerequisites.includes(other.name) ? "required" : "free"
                              }`}
                              onClick={() => togglePrerequisite(i, other.name)}
                            >
                              {other.name}
                            </button>
                          ))}
                      </div>
                    )}
                  </td>
                  <td>
                    <button
                      className="danger"
                      onClick={() =>
                        setConfig((current) => {
                          const removed = current.disciplines[i].name;
                          return {
                            ...current,
                            disciplines: current.disciplines
                              .filter((_, j) => j !== i)
                              .map((d) => ({
                                ...d,
                                prerequisites: d.prerequisites.filter((p) => p !== removed),
                              })),
                          };
                        })
                      }
                    >
                      remover
                    </button>
                  </td>
                </tr>
              );
            })}
            {config.disciplines.length === 0 && (
              <tr><td colSpan={6} className="empty-state">Nenhuma disciplina ainda.</td></tr>
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
                  {
                    name: freshName(current.disciplines),
                    seats: 20,
                    hours: 60,
                    prerequisites: [],
                  },
                ],
              }))
            }
          >
            + adicionar disciplina
          </button>
        </div>
      </div>

      <div className="actions sticky-actions">
        <button className="primary" disabled={running} onClick={onRun}>
          {comparing
            ? running
              ? `Comparando — ${runs * COMPARISON_ARMS.length} simulações...`
              : "Comparar modelos"
            : running
              ? "Simulando..."
              : "Executar simulação"}
        </button>
      </div>
      </div>

      <PresetList selected={presetId} hasCustom={hasCustom} onSelect={onSelectPreset} />
    </div>
  );
}
