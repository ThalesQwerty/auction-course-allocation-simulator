import { useMemo, useState } from "react";
import { DensityChart, STATUS } from "./charts";
import { entryDisciplines } from "./curriculum";
import { gradeDensity, utilityDensity } from "./distributions";
import { PresetList } from "./PresetList";
import { COMPARISON_ARMS, MAX_COMPARISON_RUNS } from "./types";
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

  // O recorte que cada prévia desenha. Nada disto é parâmetro de cenário: não
  // vai para a API, e por isso mora aqui e não em `Scenario`.
  const [difficulty, setDifficulty] = useState(1);
  const [attempt, setAttempt] = useState(1);
  const [relativeUtility, setRelativeUtility] = useState(1);

  // As duas distribuições de entrada, recalculadas a cada tecla. São curvas, e
  // não barras: aqui não há dado contado, e sim a forma que os parâmetros
  // implicam.
  const grades = useMemo(
    () => gradeDensity(config, { difficulty, attempt, relativeUtility }),
    [config, difficulty, attempt, relativeUtility]
  );
  const utilities = useMemo(() => utilityDensity(config), [config]);
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
              <label>Períodos (|T|)</label>
              <input
                type="number"
                min={1}
                max={40}
                value={config.periods}
                onChange={(e) => patch({ periods: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Períodos com ingresso</label>
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
              />
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Notas</h2>
          <div className="config-split">
            <div>
              <div className="field-row">
                <div className="field">
                  <label>Nota média</label>
                  {/* O cenário guarda a média da aptidão em (0, 1); a tela a
                      edita como nota, que é o mesmo número vezes 10 — em
                      dificuldade 1 e primeira tentativa a nota *é* a aptidão.
                      O arredondamento no caminho de ida evita que 0,67 apareça
                      como 6,700000000000001. */}
                  <input
                    type="number"
                    min={0.1}
                    max={9.9}
                    step={0.1}
                    value={Math.round(config.aptitude_mean * 1000) / 100}
                    onChange={(e) => patch({ aptitude_mean: Number(e.target.value) / 10 })}
                  />
                </div>
                <div className="field">
                  <label>Concentração</label>
                  <input
                    type="number"
                    min={0.5}
                    step={0.5}
                    value={config.aptitude_concentration}
                    onChange={(e) => patch({ aptitude_concentration: Number(e.target.value) })}
                  />
                </div>
              </div>

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
                title="Distribuição das notas"
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
                      <label>Dificuldade (D)</label>
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
                      <label>Tentativa (t)</label>
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
