import { useMemo } from "react";
import { CYCLIC, curriculumPeriods, entryDisciplines } from "./curriculum";
import { PresetList } from "./PresetList";
import {
  COMPARISON_ARMS,
  MAX_COMPARISON_RUNS,
} from "./types";
import type {
  DisciplineInput,
  Scenario,
} from "./types";

export function Config({
  config,
  setConfig,
  runs,
  setRuns,
  running,
  error,
  onRun,
  presetId,
  hasCustom,
  onSelectPreset,
}: {
  config: Scenario;
  setConfig: (update: (current: Scenario) => Scenario) => void;
  runs: number;
  setRuns: (runs: number) => void;
  running: boolean;
  error: string | null;
  onRun: () => void;
  presetId: string | null;
  hasCustom: boolean;
  onSelectPreset: (presetId: string | null) => void;
}) {

  function patch(values: Partial<Scenario>) {
    setConfig((current) => ({ ...current, ...values }));
  }

  function updateDiscipline(index: number, values: Partial<DisciplineInput>) {
    setConfig((current) => ({
      ...current,
      disciplines: current.disciplines.map((d, i) => (i === index ? { ...d, ...values } : d)),
    }));
  }


  const periods = useMemo(() => curriculumPeriods(config.disciplines), [config.disciplines]);
  const hasCycle = Object.values(periods).some((p) => p === CYCLIC);
  // **Entrada**, não "1º período": a optativa também não tem pré-requisito e
  // também cai no 1º período na indução, mas fica fora da matrícula garantida.
  // Validar contra o conjunto errado acusaria erro em cenário que o motor
  // aceita, e o erro cresceria com o tamanho do catálogo de optativas.
  const entryCourses = entryDisciplines(config.disciplines);
  const entryHours = entryCourses.reduce((sum, d) => sum + d.hours, 0);
  const smallestEntrySeats = entryCourses.length
    ? Math.min(...entryCourses.map((d) => d.seats))
    : 0;
  const entryTooLarge = config.students_per_period > smallestEntrySeats;
  const entryTooHeavy = entryHours > config.max_hours;

  const totalSeats = config.disciplines.reduce((sum, d) => sum + d.seats, 0);
  const totalHours = config.disciplines.reduce((sum, d) => sum + d.hours, 0);

  return (
    <div className="rail-layout">
      <div className="rail-layout-main">
      <h1>Configurar comparação</h1>

      {error && <div className="error-banner">{error}</div>}

      <div className="panel">
        <h2>Execução</h2>
        <p className="note">
          Toda execução é uma <strong>comparação entre modelos</strong>: o mesmo cenário roda nos{" "}
          {COMPARISON_ARMS.length} braços, com as seeds de 1 a N. As listas são pareadas — a
          i-ésima execução de cada braço parte da mesma população, da mesma matriz de utilidades e
          da mesma de aptidão —, e por isso a diferença entre eles é atribuível ao modelo, e não ao
          sorteio.
        </p>
        <div className="field-row">
          <div className="field">
            <label>Execuções por modelo (N)</label>
            <input
              type="number"
              min={1}
              max={MAX_COMPARISON_RUNS}
              value={runs}
              onChange={(e) => setRuns(Number(e.target.value))}
            />
            <span className="field-hint">
              {runs * COMPARISON_ARMS.length} simulações
            </span>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Configurações gerais</h2>
        <div className="field-row">
          <div className="field">
            <label>Períodos (|T|)</label>
            <input type="number" min={1} max={40} value={config.periods} onChange={(e) => patch({ periods: Number(e.target.value) })} />
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
            <span className="field-hint">vazio = todos os períodos</span>
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
            {entryTooLarge && (
              <span className="field-hint invalid-text">
                Passa das {smallestEntrySeats} vagas da disciplina de entrada mais apertada.
              </span>
            )}
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
        </div>
      </div>

      <div className="panel">
        <h2>Como são os alunos</h2>

        <div className="subpanel">
          <h3>Notas</h3>
          <p className="note">
            A nota sai da <strong>aptidão</strong> do aluno naquela disciplina, elevada à demanda
            que ela lhe faz: com dificuldade 1, primeira tentativa e sem acoplamento, o expoente é
            1 e a <em>nota é a aptidão</em>. A aptidão vem de uma Beta por par (aluno, disciplina),
            sorteada uma vez e permanente — é traço, não sorte. Dificuldade e tentativa entram como
            a razão <em>D/t</em>: dificuldade 2 na segunda tentativa equivale a dificuldade 1 na
            primeira.
          </p>
          <div className="field-row">
            <div className="field">
              <label>Aptidão: α</label>
              <input
                type="number"
                min={0.1}
                step={0.5}
                value={config.aptitude_alpha}
                onChange={(e) => patch({ aptitude_alpha: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Aptidão: β</label>
              <input
                type="number"
                min={0.1}
                step={0.5}
                value={config.aptitude_beta}
                onChange={(e) => patch({ aptitude_beta: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Ruído por tentativa</label>
              <input
                type="number"
                min={0}
                step={0.05}
                value={config.grade_noise}
                onChange={(e) => patch({ grade_noise: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Interesse × desempenho</label>
              <input
                type="number"
                min={0}
                step={0.25}
                value={config.interest_coupling}
                onChange={(e) => patch({ interest_coupling: Number(e.target.value) })}
              />
            </div>
          </div>
          <p className="note">
            <strong>Zero desliga o acoplamento</strong>, e é o padrão. Ele é a única peça da
            fórmula de nota sem forma justificada e a única que mexe no resultado principal: em 1
            ela fabrica sozinha ~40% de vão em aprovações a favor do lance, antes de qualquer
            alocação ter sido avaliada. Em 0 a função de nota é neutra entre os modelos, e
            qualquer vão em conclusões é do modelo, inteiro.
          </p>
        </div>

        <div className="subpanel">
          <h3>Utilidades</h3>
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
              <div className="field">
              <label>Parte permanente do gosto</label>
              <input
                type="number"
                min={0}
                max={1}
                step={0.1}
                value={config.utility_stability}
                onChange={(e) => patch({ utility_stability: Number(e.target.value) })}
              />
              <span className="field-hint">
                0 resorteia a preferência inteira todo período; 1 congela. É literalmente a
                correlação entre dois semestres quaisquer, e não mexe na dispersão de nenhum
                deles.
              </span>
            </div>
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
          {entryTooHeavy && (
            <p className="invalid-text">
              As {entryCourses.length} disciplinas de entrada somam {entryHours} h e não cabem em W
              <sub>a</sub>.
            </p>
          )}
        </div>
      </div>

      <div className="panel">
        <h2>
          Oferta — {config.disciplines.length} disciplinas, {totalSeats} vagas, {totalHours} h
        </h2>
        {hasCycle && (
          <div className="error-banner">
            Há um ciclo de sucessores. A simulação recusa o cenário enquanto ele existir.
          </div>
        )}

        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th style={{ width: 90 }}>Vagas</th>
              <th style={{ width: 110 }}>Carga</th>
            </tr>
          </thead>
          <tbody>
            {config.disciplines.map((discipline, i) => (
              <tr key={discipline.name}>
                <td className={periods[discipline.name] === CYCLIC ? "invalid-text" : undefined}>
                  {discipline.name}
                </td>
                <td>
                  <input
                    type="number"
                    min={0}
                    className={
                      discipline.entry && discipline.seats < config.students_per_period
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
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="actions sticky-actions">
        <button className="primary" disabled={running} onClick={onRun}>
          {running
            ? `Comparando — ${runs * COMPARISON_ARMS.length} simulações...`
            : "Comparar modelos"}
        </button>
      </div>
      </div>

      <PresetList selected={presetId} hasCustom={hasCustom} onSelect={onSelectPreset} />
    </div>
  );
}
