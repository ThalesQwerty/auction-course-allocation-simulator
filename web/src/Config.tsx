import { useMemo, useState } from "react";
import { DensityChart, STATUS } from "./charts";
import { entryDisciplines } from "./curriculum";
import { availabilityCurve, gradeCurve, utilityCurve } from "./distributions";
import { PresetList } from "./PresetList";
import { nameExists } from "./savedPresets";
import type { SavedPreset } from "./savedPresets";
import { ProfileList, axisShare } from "./ProfileList";
import { SaveScenario } from "./SaveScenario";
import { COMPARISON_ARMS, MAX_COMPARISON_RUNS, horizonFor } from "./types";
import type { Scenario } from "./types";

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
  saved,
  onSave,
  onDeleteSaved,
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
  saved: SavedPreset[];
  /** Grava o cenário atual sob este nome. Nome que já existe **substitui** o
   * cenário daquele nome — é assim que se edita um salvo. */
  onSave: (name: string) => void;
  onDeleteSaved: (presetId: string) => void;
}) {
  function patch(values: Partial<Scenario>) {
    setConfig((current) => ({ ...current, ...values }));
  }

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
  // |T| não se configura: sai do ciclo de vida da população. Depois que a
  // última geração sai — concluída ou jubilada — não há mais ninguém a simular.
  const horizon = horizonFor(config.entry_periods, config.max_residence);
  const entryTooHeavy = entryHours > config.max_hours;

  // O recorte que cada prévia desenha. Nada disto é parâmetro de cenário: não
  // vai para a API, e por isso mora aqui e não em `Scenario`.
  const [difficulty, setDifficulty] = useState(1);
  const [attempt, setAttempt] = useState(1);
  const [relativeUtility, setRelativeUtility] = useState(1);
  const [attractiveness, setAttractiveness] = useState(0);
  // Qual linha do editor a prévia ao lado desenha. Uma curva por vez, em vez
  // de todas sobrepostas: com cinco ou seis grupos aquilo vira emaranhado.
  const [performanceIndex, setPerformanceIndex] = useState(0);
  const [availabilityIndex, setAvailabilityIndex] = useState(0);

  const performance =
    config.performance_profiles[performanceIndex] ?? config.performance_profiles[0];
  const availability =
    config.availability_profiles[availabilityIndex] ?? config.availability_profiles[0];

  // As duas distribuições de entrada, recalculadas a cada tecla. São curvas, e
  // não barras: aqui não há dado contado, e sim a forma que os parâmetros
  // implicam.
  const grades = useMemo(
    () => gradeCurve(config, { difficulty, attempt, relativeUtility }, performance),
    [config, difficulty, attempt, relativeUtility, performance]
  );
  const availabilities = useMemo(
    () => availabilityCurve(availability),
    [availability]
  );
  const utilities = useMemo(
    () => utilityCurve(config, attractiveness),
    [config, attractiveness]
  );
  // O eixo da utilidade é o suporte da própria amostra, que a curva já carrega
  // no último ponto.
  const utilityTop = utilities.points.length
    ? utilities.points[utilities.points.length - 1].x
    : 1;
  // Uma casa a mais do que a régua do eixo: o rodapé dá um número, e um número
  // arredondado à casa do eixo perderia justamente o que ele acrescenta.
  const utilityDigits =
    Math.max(0, Math.ceil(-Math.log10(Math.max(utilityTop, 1e-9) / 10))) + 1;
  const utilityValue = (value: number) =>
    value.toLocaleString("pt-BR", { maximumFractionDigits: utilityDigits });

  // O nome proposto ao salvar. Vindo de um preset carregado, é o nome dele —
  // salvar por cima de um salvo é o caminho de edição, e repetir o nome é
  // justamente o que o usuário quer ali. Do contrário, a data basta para
  // distinguir.
  const suggestedName =
    saved.find((entry) => entry.id === presetId)?.name ??
    `Cenário de ${new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}`;

  // O rodapé de cada seção fala do **próprio** eixo: a lista ali edita os
  // grupos de um só, e a fatia que interessa é a dele. A contagem de
  // combinações vem junto, nomeando o outro eixo.
  const performanceShare = axisShare(
    config.performance_profiles.length,
    config.availability_profiles.length
  );
  const availabilityShare = axisShare(
    config.availability_profiles.length,
    config.performance_profiles.length
  );

  // A nota sai do motor arredondada a um décimo; o rodapé a mostra assim.
  const grade = (value: number) =>
    value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });


  return (
    <div className="rail-layout">
      <div className="rail-layout-main">
        <h1>Configurar comparação</h1>

        {error && <div className="error-banner">{error}</div>}

        <div className="panel">
          <h2>Configurações gerais</h2>
          <div className="field-row">
            <div className="field">
              <label>Execuções por modelo</label>
              <input
                type="number"
                min={1}
                max={MAX_COMPARISON_RUNS}
                value={runs}
                onChange={(e) => setRuns(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="field-row">
            <div className="field">
              <label>Períodos com ingresso</label>
              <input
                type="number"
                min={1}
                max={40}
                value={config.entry_periods}
                onChange={(e) => patch({ entry_periods: Number(e.target.value) })}
              />
              <span className="field-hint">
                Quantas gerações entram. Depois da última vem a drenagem.
              </span>
            </div>
            <div className="field">
              <label>Jubilamento</label>
              <input
                type="number"
                min={1}
                max={40}
                value={config.max_residence}
                onChange={(e) => patch({ max_residence: Number(e.target.value) })}
              />
              <span className="field-hint">
                Períodos para concluir. Daí <strong>|T| = {horizon}</strong>: é quando a
                última geração sai, e depois dela não há mais quem simular.
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
              {entryTooLarge && (
                <span className="field-hint invalid-text">
                  Passa das {smallestEntrySeats} vagas da disciplina de entrada mais apertada.
                </span>
              )}
            </div>
          </div>

          <div className="field-row">
            <div className="field">
              <label>Rodadas por período (|R|)</label>
              <input
                type="number"
                min={1}
                max={10}
                value={config.rounds}
                onChange={(e) => patch({ rounds: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>
                Créditos base por período (Γ<sub>min</sub>)
              </label>
              <input
                type="number"
                min={1}
                value={config.base_credits}
                onChange={(e) => patch({ base_credits: Number(e.target.value) })}
              />
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Utilidades</h2>
          <div className="config-split">
            <div>
              <div className="field-row">
                <div className="field">
                  <label>Desvio da log-normal</label>
                  <input
                    type="number"
                    min={0.05}
                    step={0.05}
                    value={config.utility_sigma}
                    onChange={(e) => patch({ utility_sigma: Number(e.target.value) })}
                  />
                </div>
                <div className="field">
                  <label>Estabilidade</label>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.1}
                    value={config.utility_stability}
                    onChange={(e) => patch({ utility_stability: Number(e.target.value) })}
                  />
                </div>
              </div>

              <div className="field-row">
                <div className="field">
                  <label>
                    Carga horária máxima (W<sub>a</sub>)
                  </label>
                  <input
                    type="number"
                    min={30}
                    step={30}
                    className={entryTooHeavy ? "invalid" : undefined}
                    value={config.max_hours}
                    onChange={(e) => patch({ max_hours: Number(e.target.value) })}
                  />
                </div>
              </div>

              {entryTooHeavy && (
                <p className="invalid-text">
                  As {entryCourses.length} disciplinas de entrada somam {entryHours} h e não cabem
                  em W<sub>a</sub>.
                </p>
              )}
            </div>

            <div className="config-preview">
              <DensityChart
                id="curva-utilidade"
                title="Distribuição de utilidade relativa"
                points={utilities.points}
                domain={[0, utilityTop]}
                footer={<>mais provável: {utilityValue(utilities.mode)}</>}
                controls={
                  <div className="field-row">
                    <div className="field">
                      <label>Atratividade</label>
                      {/* O recorte, não o cenário: a curva é a de uma
                          disciplina com esta atratividade quando as demais
                          estão em 0. No cenário ela é declarada por
                          disciplina. Sem `min`: o eixo é ℝ inteiro, e
                          negativo é gosto abaixo da disciplina média. */}
                      <input
                        type="number"
                        step={0.1}
                        value={attractiveness}
                        onChange={(e) => setAttractiveness(Number(e.target.value))}
                      />
                    </div>
                  </div>
                }
              />
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Notas</h2>
          <div className="config-split">
            <div>
              <ProfileList
                profiles={config.performance_profiles}
                onChange={(performance_profiles) => patch({ performance_profiles })}
                selected={performanceIndex}
                onSelect={setPerformanceIndex}
                scale="grade"
                newName="desempenho"
              />

              <div className="field-row">
                <div className="field">
                  <label>Ganho por utilidade</label>
                  <input
                    type="number"
                    min={0}
                    step={0.25}
                    value={config.utility_gain}
                    onChange={(e) => patch({ utility_gain: Number(e.target.value) })}
                  />
                </div>
                <div className="field">
                  <label>Ganho por tentativa</label>
                  <input
                    type="number"
                    min={0}
                    step={0.25}
                    value={config.retake_gain}
                    onChange={(e) => patch({ retake_gain: Number(e.target.value) })}
                  />
                </div>
              </div>

              <div className="field-row">
                <div className="field">
                  <label>
                    Nota mínima de aprovação (n<sub>min</sub>)
                  </label>
                  <input
                    type="number"
                    min={0.1}
                    max={10}
                    step={0.1}
                    value={config.min_grade}
                    onChange={(e) => patch({ min_grade: Number(e.target.value) })}
                  />
                </div>
              </div>
            </div>

            <div className="config-preview">
              <DensityChart
                id="curva-notas"
                title={`Notas — ${performance.name}`}
                points={grades.points}
                domain={[0, 10]}
                footer={
                  <>
                    mais provável: {grade(grades.mode)} · aprova: {" "}
                    {(grades.approval * 100).toLocaleString("pt-BR", {
                      maximumFractionDigits: 1,
                    })}
                    %
                  </>
                }
                split={{
                  at: config.min_grade,
                  below: STATUS.critical,
                  above: STATUS.good,
                  labels: ["reprova", "aprova"],
                }}
                controls={
                  <div className="field-row">
                    <div className="field">
                      <label>Dificuldade</label>
                      {/* O min é a base da escada do stepper: com min 0 e passo
                          0,1 a grade é 0 · 0,1 · 0,2, e o padrão (1) cai nela.
                          O 0 é aparado na prévia. */}
                      <input
                        type="number"
                        min={0}
                        step={0.1}
                        value={difficulty}
                        onChange={(e) => setDifficulty(Number(e.target.value))}
                      />
                    </div>
                    <div className="field">
                      <label>Tentativa</label>
                      <input
                        type="number"
                        min={1}
                        step={1}
                        value={attempt}
                        onChange={(e) =>
                          setAttempt(Math.max(1, Math.round(Number(e.target.value))))
                        }
                      />
                    </div>
                    <div className="field">
                      <label>Utilidade relativa</label>
                      <input
                        type="number"
                        min={0.0001}
                        step={0.1}
                        value={relativeUtility}
                        onChange={(e) => setRelativeUtility(Number(e.target.value))}
                      />
                    </div>
                  </div>
                }
              />
            </div>
          </div>
          <p className="note">{performanceShare}</p>
        </div>

        <div className="panel">
          <h2>Disponibilidade</h2>
          <div className="config-split">
            <div>
              <ProfileList
                profiles={config.availability_profiles}
                onChange={(availability_profiles) => patch({ availability_profiles })}
                selected={availabilityIndex}
                onSelect={setAvailabilityIndex}
                scale="fraction"
                newName="disponibilidade"
              />
            </div>

            <div className="config-preview">
              <DensityChart
                id="curva-disponibilidade"
                title={`Disponibilidade — ${availability.name}`}
                points={availabilities.points}
                domain={[0, 1]}
                footer={
                  <>
                    mais provável:{" "}
                    {availabilities.mode.toLocaleString("pt-BR", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{" "}
                    · teto típico:{" "}
                    {Math.round(availabilities.mode * config.max_hours)} h de{" "}
                    {config.max_hours}
                  </>
                }
              />
            </div>
          </div>
          <p className="note">{availabilityShare}</p>
        </div>

        <div className="actions sticky-actions">
          <button className="primary" disabled={running} onClick={onRun}>
            {running
              ? `Comparando — ${runs * COMPARISON_ARMS.length} simulações...`
              : "Comparar modelos"}
          </button>
          <div className="actions-right">
            <SaveScenario
              onSave={onSave}
              suggestion={suggestedName}
              exists={(name) => nameExists(saved, name)}
            />
          </div>
        </div>
      </div>

      <PresetList
        selected={presetId}
        hasCustom={hasCustom}
        saved={saved}
        onSelect={onSelectPreset}
        onDelete={onDeleteSaved}
      />
    </div>
  );
}
