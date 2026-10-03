import { useMemo, useState } from "react";
import { CYCLIC, curriculumLength, curriculumPeriods } from "./curriculum";
import { PresetList } from "./PresetList";
import { generationMix } from "./profiles";
import { AFFINITY_KINDS, CREDIT_RETURN_POLICIES, MAX_AFFINITY_INTENSITY, affinityExponent } from "./types";
import type {
  AffinityKind,
  AffinityProfileInput,
  AptitudeProfileInput,
  CreditReturnPolicy,
  DisciplineInput,
  SimulateRequest,
} from "./types";

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
  // Qual disciplina está com o editor de pré-requisitos aberto. Uma de cada
  // vez: 36 grades de chips abertas ao mesmo tempo não se leem.
  const [editingPrerequisites, setEditingPrerequisites] = useState<string | null>(null);

  function patch(values: Partial<SimulateRequest>) {
    setConfig((current) => ({ ...current, ...values }));
  }

  /** Edita um perfil de um dos dois eixos. Os dois têm a mesma forma — nome,
   * parâmetros e fatia —, então a mesma função serve aos dois com a chave do
   * eixo. */
  function updateProfile<K extends "aptitude_profiles" | "affinity_profiles">(
    axis: K,
    index: number,
    values: Partial<SimulateRequest[K][number]>
  ) {
    setConfig((current) => ({
      ...current,
      [axis]: current[axis].map((p, i) => (i === index ? { ...p, ...values } : p)),
    }));
  }
  function removeProfile(axis: "aptitude_profiles" | "affinity_profiles", index: number) {
    setConfig((current) => ({
      ...current,
      [axis]: current[axis].filter((_, i) => i !== index),
    }));
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

  const periods = useMemo(() => curriculumPeriods(config.disciplines), [config.disciplines]);
  const hasCycle = Object.values(periods).some((p) => p === CYCLIC);
  const gradeLength = curriculumLength(config.disciplines);
  const firstPeriod = config.disciplines.filter((d) => periods[d.name] === 1);
  const entryHours = firstPeriod.reduce((sum, d) => sum + d.hours, 0);
  // W_a é por perfil de afinidade. A matrícula garantida não escolhe quem a
  // recebe, então ela tem de caber no perfil mais apertado; o piso de períodos,
  // ao contrário, é do aluno mais rápido possível, e vale o mais folgado.
  const workloads = config.affinity_profiles.map((p) => p.max_hours);
  const tightestWorkload = workloads.length ? Math.min(...workloads) : 0;
  const roomiestWorkload = workloads.length ? Math.max(...workloads) : 0;
  // O ingressante entra direto em todas as de 1º período: a geração tem de
  // caber na menor oferta delas, e a carga somada tem de caber em W_a (eq. 4).
  const smallestEntrySeats = firstPeriod.length
    ? Math.min(...firstPeriod.map((d) => d.seats))
    : 0;
  const entryTooLarge = config.students_per_period > smallestEntrySeats;
  const entryTooHeavy = entryHours > tightestWorkload;

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
    Math.ceil(totalHours / Math.max(roomiestWorkload, 1)),
    gradeLength
  );

  // As fatias de cada eixo repartem a população inteira, então somam 100%. O
  // motor recusa o cenário fora disso — normalizar em silêncio esconderia um
  // erro de digitação que muda o cenário sem avisar.
  const aptitudeShare = config.aptitude_profiles.reduce((sum, p) => sum + p.share, 0);
  const affinityShare = config.affinity_profiles.reduce((sum, p) => sum + p.share, 0);
  const sharesOk = (total: number) => Math.abs(total - 100) < 1e-6;
  const mix = useMemo(
    () =>
      generationMix(
        config.students_per_period,
        config.aptitude_profiles,
        config.affinity_profiles
      ),
    [config.students_per_period, config.aptitude_profiles, config.affinity_profiles]
  );

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
              horizonte antes de poderem se formar. Piso teórico para concluir:{" "}
              {floorPeriods} períodos — o maior entre ⌈{totalHours} h ÷ {roomiestWorkload} h⌉ e os{" "}
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
        <h2>Perfis de aluno</h2>
        <p className="note">
          Dois eixos <strong>independentes</strong>: a aptidão dá a distribuição das notas e a
          afinidade distorce a matriz de utilidades. Como são independentes, a fatia de uma
          combinação é o produto das duas — dois perfis de 50% em cada eixo dão 25% para cada uma
          das quatro combinações. A repartição é exata e idêntica em toda geração: sem isso o
          perfil ficaria correlacionado com o período de ingresso, e o recorte por geração passaria
          a medir perfil junto com senioridade.
        </p>

        <div className="subpanel">
          <h3>
            Aptidão — a normal das notas e o que a recursada acrescenta{" "}
            <span className={sharesOk(aptitudeShare) ? "muted-cell" : "invalid-text"}>
              ({aptitudeShare.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}% de 100%)
            </span>
          </h3>
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th style={{ width: 100 }}>Média</th>
                <th style={{ width: 120 }}>Desvio padrão</th>
                <th style={{ width: 150 }}>Ganho por recursada</th>
                <th style={{ width: 110 }}>% dos alunos</th>
                <th style={{ width: 90 }} />
              </tr>
            </thead>
            <tbody>
              {config.aptitude_profiles.map((profile, i) => (
                <tr key={i}>
                  <td>
                    <input
                      value={profile.name}
                      onChange={(e) =>
                        updateProfile("aptitude_profiles", i, { name: e.target.value })
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      step={0.1}
                      value={profile.mean}
                      onChange={(e) =>
                        updateProfile("aptitude_profiles", i, { mean: Number(e.target.value) })
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min={0.1}
                      step={0.1}
                      value={profile.stddev}
                      onChange={(e) =>
                        updateProfile("aptitude_profiles", i, { stddev: Number(e.target.value) })
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min={0.1}
                      max={10}
                      step={0.1}
                      value={profile.learning_gain}
                      onChange={(e) =>
                        updateProfile("aptitude_profiles", i, {
                          learning_gain: Number(e.target.value),
                        })
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step={1}
                      className={sharesOk(aptitudeShare) ? undefined : "invalid"}
                      value={profile.share}
                      onChange={(e) =>
                        updateProfile("aptitude_profiles", i, { share: Number(e.target.value) })
                      }
                    />
                  </td>
                  <td>
                    <button
                      className="danger"
                      disabled={config.aptitude_profiles.length === 1}
                      onClick={() => removeProfile("aptitude_profiles", i)}
                    >
                      remover
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="actions">
            <button
              className="secondary"
              onClick={() =>
                setConfig((current) => ({
                  ...current,
                  aptitude_profiles: [
                    ...current.aptitude_profiles,
                    {
                      name: `Aptidão ${current.aptitude_profiles.length + 1}`,
                      mean: 6.5,
                      stddev: 1.5,
                      learning_gain: 2.5,
                      share: 0,
                    } satisfies AptitudeProfileInput,
                  ],
                }))
              }
            >
              + adicionar perfil de aptidão
            </button>
          </div>
        </div>

        <div className="subpanel">
          <h3>
            Afinidade — o expoente sobre as utilidades e a carga que o aluno carrega{" "}
            <span className={sharesOk(affinityShare) ? "muted-cell" : "invalid-text"}>
              ({affinityShare.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}% de 100%)
            </span>
          </h3>
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th style={{ width: 140 }}>Tipo de interesse</th>
                <th style={{ width: 105 }}>Intensidade</th>
                <th style={{ width: 95 }}>Expoente</th>
                <th style={{ width: 150 }}>
                  Carga máxima (W<sub>a</sub>)
                </th>
                <th style={{ width: 110 }}>% dos alunos</th>
                <th style={{ width: 90 }} />
              </tr>
            </thead>
            <tbody>
              {config.affinity_profiles.map((profile, i) => (
                <tr key={i}>
                  <td>
                    <input
                      value={profile.name}
                      onChange={(e) =>
                        updateProfile("affinity_profiles", i, { name: e.target.value })
                      }
                    />
                  </td>
                  <td>
                    <select
                      value={profile.kind}
                      onChange={(e) =>
                        updateProfile("affinity_profiles", i, {
                          kind: e.target.value as AffinityKind,
                        })
                      }
                    >
                      {AFFINITY_KINDS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      min={1}
                      max={MAX_AFFINITY_INTENSITY}
                      step={1}
                      value={profile.intensity}
                      onChange={(e) =>
                        updateProfile("affinity_profiles", i, {
                          intensity: Number(e.target.value),
                        })
                      }
                    />
                  </td>
                  {/* Derivado, não editável: é o que a intensidade e o tipo
                      significam juntos, e vê-lo evita confundir "diluído 2"
                      com expoente 2. */}
                  <td className="muted-cell">
                    {profile.kind === "concentrated"
                      ? profile.intensity
                      : `1/${profile.intensity}`}{" "}
                    ={" "}
                    {affinityExponent(profile).toLocaleString("pt-BR", {
                      maximumFractionDigits: 3,
                    })}
                  </td>
                  <td>
                    <input
                      type="number"
                      min={1}
                      step={10}
                      className={entryHours > profile.max_hours ? "invalid" : undefined}
                      value={profile.max_hours}
                      onChange={(e) =>
                        updateProfile("affinity_profiles", i, {
                          max_hours: Number(e.target.value),
                        })
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step={1}
                      className={sharesOk(affinityShare) ? undefined : "invalid"}
                      value={profile.share}
                      onChange={(e) =>
                        updateProfile("affinity_profiles", i, { share: Number(e.target.value) })
                      }
                    />
                  </td>
                  <td>
                    <button
                      className="danger"
                      disabled={config.affinity_profiles.length === 1}
                      onClick={() => removeProfile("affinity_profiles", i)}
                    >
                      remover
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="actions">
            <button
              className="secondary"
              onClick={() =>
                setConfig((current) => ({
                  ...current,
                  affinity_profiles: [
                    ...current.affinity_profiles,
                    {
                      name: `Afinidade ${current.affinity_profiles.length + 1}`,
                      kind: "concentrated",
                      intensity: 1,
                      max_hours: tightestWorkload || 360,
                      share: 0,
                    } satisfies AffinityProfileInput,
                  ],
                }))
              }
            >
              + adicionar perfil de afinidade
            </button>
          </div>
          <p className="note">
            {AFFINITY_KINDS.map((kind) => `${kind.label}: ${kind.hint}`).join(" · ")}.
            Intensidade 1 é o perfil neutro — expoente 1 nos dois sentidos, sem distorção. Depois
            da distorção a matriz é dividida pelo somatório, de modo que U<sub>a</sub> continue
            valendo a eq. (43).{" "}
            {entryTooHeavy ? (
              <span className="invalid-text">
                As {firstPeriod.length} disciplinas de 1º período somam {entryHours} h e não cabem
                na carga máxima de todo perfil — o ingressante cursa todas de uma vez, e a eq. (4)
                tem de continuar valendo.
              </span>
            ) : (
              <>
                A carga máxima (W<sub>a</sub>) precisa comportar as {firstPeriod.length}{" "}
                disciplinas de 1º período, que somam {entryHours} h: é a matrícula garantida de
                quem ingressa, e ela não escolhe perfil.
              </>
            )}
          </p>
        </div>

        <div className="subpanel">
          <h3>Composição de cada geração — {config.students_per_period} alunos</h3>
          <p className="note">
            A repartição inteira é feita sobre a combinação, não eixo a eixo: repartir cada eixo e
            cruzar depois não garante o produto. Sobras de arredondamento vão às maiores frações,
            então uma fatia pode não cair exata quando a geração é pequena.
          </p>
          <table>
            <thead>
              <tr>
                <th>Aptidão</th><th>Afinidade</th>
                <th style={{ width: 110 }}>Fatia</th>
                <th style={{ width: 150 }}>Alunos por geração</th>
              </tr>
            </thead>
            <tbody>
              {mix.map((combination) => (
                <tr key={`${combination.aptitude}|${combination.affinity}`}>
                  <td>{combination.aptitude}</td>
                  <td>{combination.affinity}</td>
                  <td className="muted-cell">
                    {combination.share.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%
                  </td>
                  <td>{combination.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
          {running ? "Simulando..." : "Executar simulação"}
        </button>
      </div>
      </div>

      <PresetList selected={presetId} hasCustom={hasCustom} onSelect={onSelectPreset} />
    </div>
  );
}
