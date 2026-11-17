import { useMemo, useState } from "react";
import { DensityChart, LineSample, STATUS } from "./charts";
import { entryDisciplines } from "./curriculum";
import { availabilityCurve, gradeCurve, interestCurve } from "./distributions";
import {
  cohortSize,
  entryClassLoad,
  fullLoadThreshold,
  profileCombinations,
  schedulePressure,
} from "./equations";
import { PresetList } from "./PresetList";
import { nameExists } from "./savedPresets";
import type { SavedPreset } from "./savedPresets";
import {
  AvailabilityProfileList,
  PerformanceProfileList,
  RoutineProfileList,
  StrategyProfileList,
  axisShare,
} from "./ProfileList";
import { SaveScenario } from "./SaveScenario";
import { COMPARISON_ARMS, MAX_COMPARISON_RUNS } from "./types";
import type { Scenario } from "./types";

/** Quantas turmas caem em cada horário, lido como faixa. É o número que diz
 * se mexer nos horários apertou o conflito: menos horários é mais turma por
 * horário, e mais escolha do aluno travada por choque. */
const scheduleLoad = (config: Scenario): string => {
  const load = schedulePressure(
    config.disciplines,
    config.day_slots,
    config.night_slots
  );
  const faixa = (counts: number[]) => {
    const low = Math.min(...counts);
    const high = Math.max(...counts);
    return low === high ? `${low}` : `${low}–${high}`;
  };
  return (
    `${faixa(load.day)} turmas por horário diurno · ` +
    `${faixa(load.night)} por noturno`
  );
};

export function Config({
  config,
  setConfig,
  runs,
  setRuns,
  arms,
  setArms,
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
  arms: string[];
  setArms: (arms: string[]) => void;
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
  const cohort = cohortSize(config);
  // Por **turma**: a matrícula garantida reparte a coorte entre as turmas de
  // cada disciplina de entrada, e o que precisa caber é o maior desses
  // blocos — não a coorte inteira.
  const biggestEntryBlock = entryCourses.length
    ? Math.max(
        ...entryCourses.map((d) => Math.max(...entryClassLoad(cohort, d.classes)))
      )
    : 0;
  const entryTooLarge = biggestEntryBlock > config.class_size;
  // Quantos calouros a oferta de entrada comporta: a disciplina de entrada com
  // menos turmas é o gargalo. Os blocos são equilibrados, então a coorte cabe
  // exatamente quando não passa disto.
  const entrySeats = entryCourses.length
    ? Math.min(...entryCourses.map((d) => d.classes)) * config.class_size
    : 0;
  const entryTooHeavy = entryHours > config.max_hours;

  // Porcentagem com casas suficientes para 0,05% não virar 0%: as chances de
  // ponta vivem entre centésimos de ponto e dezenas.
  const percent = (share: number) =>
    `${(share * 100).toLocaleString("pt-BR", { maximumSignificantDigits: 2 })}%`;

  // O recorte que cada prévia desenha. Nada disto é parâmetro de cenário: não
  // vai para a API, e por isso mora aqui e não em `Scenario`.
  const [difficulty, setDifficulty] = useState(1);
  const [attempt, setAttempt] = useState(1);
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
    () => gradeCurve(config, { difficulty, attempt }, performance),
    [config, difficulty, attempt, performance]
  );
  // Em horas, não em fração: o parâmetro é uma fração de W_a, mas quem lê a
  // curva quer saber quanta carga ela permite.
  const availabilities = useMemo(
    () => availabilityCurve(availability, config.max_hours),
    [availability, config.max_hours]
  );
  const interest = useMemo(
    () => interestCurve(config),
    [config]
  );
  // O eixo do interesse é o suporte da própria amostra, que a curva já carrega
  // no último ponto.
  const interestTop = interest.points.length
    ? interest.points[interest.points.length - 1].x
    : 1;
  // Uma casa a mais do que a régua do eixo: o rodapé dá um número, e um número
  // arredondado à casa do eixo perderia justamente o que ele acrescenta.
  const interestDigits =
    Math.max(0, Math.ceil(-Math.log10(Math.max(interestTop, 1e-9) / 10))) + 1;
  const interestValue = (value: number) =>
    value.toLocaleString("pt-BR", { maximumFractionDigits: interestDigits });

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
  const performanceShare = axisShare(config.performance_profiles.length);
  const availabilityShare = axisShare(config.availability_profiles.length);

  // O catálogo de optativas é maior que a exigência de propósito — é a folga
  // que dá ao aluno o que escolher —, e exigir mais do que se oferta deixaria
  // o curso sem saída. É o mesmo limite que `SimulationConfig` impõe.
  const electiveOffer = config.disciplines.reduce(
    (total, discipline) => total + (discipline.elective ? discipline.hours : 0),
    0
  );
  const electiveTooLarge = config.elective_hours > electiveOffer;

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
              <label>Modelos</label>
              <div className="checkbox-set">
                {COMPARISON_ARMS.map((arm) => {
                  const on = arms.includes(arm.key);
                  return (
                    <label className="checkbox" key={arm.key}>
                      <input
                        type="checkbox"
                        checked={on}
                        /* O último marcado não se desmarca: sem braço nenhum
                           não há o que rodar, e o motor recusaria o pedido. */
                        disabled={on && arms.length === 1}
                        onChange={() =>
                          setArms(
                            COMPARISON_ARMS.filter((other) =>
                              other.key === arm.key ? !on : arms.includes(other.key)
                            ).map((other) => other.key)
                          )
                        }
                      />
                      <LineSample dash={arm.dash} color="currentColor" />
                      {arm.label}
                    </label>
                  );
                })}
              </div>
            </div>
            <div className="field">
              <label>Simulações por modelo</label>
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
            </div>
            <div className="field">
              <label>
                Carga de optativas para concluir (X)
              </label>
              <input
                type="number"
                min={0}
                step={1}
                className={electiveTooLarge ? "invalid" : undefined}
                value={config.elective_hours}
                onChange={(e) => patch({ elective_hours: Number(e.target.value) })}
              />
              {electiveTooLarge && (
                <span className="field-hint invalid-text">
                  O catálogo oferta {electiveOffer} h em optativas.
                </span>
              )}
            </div>
            <div className="field">
              <label>Exemplares por perfil</label>
              <input
                type="number"
                min={1}
                className={entryTooLarge ? "invalid" : undefined}
                value={config.students_per_profile}
                onChange={(e) => patch({ students_per_profile: Number(e.target.value) })}
              />
              {entryTooLarge && (
                <span className="field-hint invalid-text">
                  A coorte põe {biggestEntryBlock} ingressantes numa turma de{" "}
                  {config.class_size} vagas.
                </span>
              )}
            </div>
            <div className="field">
              <label>Alunos por turma</label>
              <input
                type="number"
                min={1}
                value={config.class_size}
                onChange={(e) => patch({ class_size: Number(e.target.value) })}
              />
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
                Orçamento mínimo (C<sub>min</sub>)
              </label>
              <input
                type="number"
                min={1}
                value={config.min_credits}
                onChange={(e) => patch({ min_credits: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>
                Orçamento máximo (C<sub>max</sub>)
              </label>
              <input
                type="number"
                min={config.min_credits}
                value={config.max_credits ?? config.min_credits}
                onChange={(e) => patch({ max_credits: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Multiplicador do retorno (k)</label>
              <input
                type="number"
                min={0}
                step={0.5}
                value={config.return_multiplier}
                onChange={(e) =>
                  patch({ return_multiplier: Number(e.target.value) })
                }
              />
            </div>
            <div className="field">
              <label>Retorno da excluída (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                step={5}
                value={Math.round(config.exclusion_refund_rate * 100)}
                onChange={(e) =>
                  patch({ exclusion_refund_rate: Number(e.target.value) / 100 })
                }
              />
            </div>
          </div>

          <p className="note">
            Coorte de {cohort} ({profileCombinations(config)} combinações de
            perfil) · {entrySeats} vagas de ingresso ·{" "}
            {cohort * config.entry_periods} alunos no total
          </p>
        </div>

        <div className="panel">
          <h2>Interesse</h2>
          <div className="config-split">
            <div>
              <div className="field-row">
                <div className="field">
                  <label>Média da log-normal</label>
                  {/* Sem `min`: μ é ℝ inteiro, e não mexe em alocação — some
                      na normalização. Serve à prévia ao lado. */}
                  <input
                    type="number"
                    step={0.1}
                    value={config.interest_mean}
                    onChange={(e) => patch({ interest_mean: Number(e.target.value) })}
                  />
                </div>
                <div className="field">
                  <label>Desvio da log-normal</label>
                  <input
                    type="number"
                    min={0.05}
                    step={0.05}
                    value={config.interest_sigma}
                    onChange={(e) => patch({ interest_sigma: Number(e.target.value) })}
                  />
                </div>
                <div className="field">
                  <label>Estabilidade entre períodos</label>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.1}
                    value={config.interest_stability}
                    onChange={(e) => patch({ interest_stability: Number(e.target.value) })}
                  />
                </div>
                <div className="field">
                  <label>Estabilidade entre turmas</label>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.1}
                    value={config.class_stability}
                    onChange={(e) => patch({ class_stability: Number(e.target.value) })}
                  />
                </div>
              </div>
            </div>

            <div className="config-preview">
              <DensityChart
                id="curva-interesse"
                title="Log-normal fonte do interesse"
                points={interest.points}
                domain={[0, interestTop]}
                footer={<>mais provável: {interestValue(interest.mode)}</>}
              />
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Disponibilidade</h2>
          <div className="config-split">
            <div>
              {/* W_a fica aqui porque é o teto que a fração recorta: o perfil
                  diz que parte dele o aluno cursa, e os dois só se leem
                  juntos. */}
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

              <AvailabilityProfileList
                profiles={config.availability_profiles}
                onChange={(availability_profiles) => patch({ availability_profiles })}
                selected={availabilityIndex}
                onSelect={setAvailabilityIndex}
                top={config.max_hours}
              />
            </div>

            <div className="config-preview">
              <DensityChart
                id="curva-disponibilidade"
                title={`Disponibilidade — ${availability.name}`}
                points={availabilities?.points ?? []}
                /* O eixo **passa de W_a** de propósito: a massa à direita da
                   carga máxima é justamente a chance de alcançá-la. Parar no
                   teto faria a curva parecer truncada ali, que é exatamente o
                   que o modelo deixou de fazer. */
                domain={[0, availabilities?.top ?? config.max_hours]}
                // O motor arredonda — a carga efetiva é `round(δ)` —, então o
                // tooltip dá a hora inteira que a simulação vai usar.
                format={(value) => `${Math.round(value)} h`}
                split={{
                  // A divisa é `W_a − 0,5`, e não W_a: a carga efetiva
                  // arredonda, então 29,6 h já enche uma carga de 30 h. É o
                  // limiar que a própria log-normal inverte, e é o que faz a
                  // etiqueta concordar com a hora que o tooltip mostra.
                  at: fullLoadThreshold(config.max_hours),
                  below: STATUS.critical,
                  above: STATUS.good,
                  labels: ["não usa toda a CH máx", "usa toda a CH máx"],
                }}
                footer={
                  availabilities ? (
                    <>
                      mais provável: {Math.round(availabilities.mode)} h · enche
                      a carga: {percent(availabilities.fullLoad)}
                    </>
                  ) : (
                    <>a moda precisa ficar abaixo de W<sub>a</sub></>
                  )
                }
              />
            </div>
          </div>
          <p className="note">{availabilityShare}</p>
        </div>

        <div className="panel">
          <h2>Notas</h2>
          <div className="config-split">
            <div>
              <PerformanceProfileList
                profiles={config.performance_profiles}
                onChange={(performance_profiles) => patch({ performance_profiles })}
                selected={performanceIndex}
                onSelect={setPerformanceIndex}
              />

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
                points={grades?.points ?? []}
                domain={[0, 10]}
                /* As duas chances de ponta vão no rodapé, e não ao lado dos
                   campos, porque **mudam com o recorte**: as do perfil valem
                   para dificuldade 1 na primeira tentativa, e o que o rodapé
                   mostra é o que aquela disciplina de fato produz. A aprovação
                   também é derivada, não entrada. */
                footer={
                  grades ? (
                    <>
                      mais provável: {grade(grades.mode)} · aprova:{" "}
                      {percent(grades.approval)} · tira 0:{" "}
                      {percent(grades.zeroRate)} · tira 10:{" "}
                      {percent(grades.maxRate)}
                    </>
                  ) : (
                    <>nota média fora do alcance destas chances</>
                  )
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
                  </div>
                }
              />
            </div>
          </div>
          <p className="note">{performanceShare}</p>
        </div>

        {/* O eixo de estratégia, com seu painel como os de traço. Sem
            prévia: o valor é uma regra de decisão, não uma distribuição, e
            não há curva a desenhar. */}
        <div className="panel">
          <h2>Seletividade</h2>
          <StrategyProfileList
            profiles={config.selectivity_profiles}
            onChange={(selectivity_profiles) => patch({ selectivity_profiles })}
            label="Seletividade"
            base="seletividade"
            min={0}
            step={0.5}
            fallback={0}
          />
          <p className="note">{axisShare(config.selectivity_profiles.length)}</p>
        </div>

        <div className="panel">
          <h2>Rotina</h2>
          <RoutineProfileList
            profiles={config.routine_profiles}
            onChange={(routine_profiles) => patch({ routine_profiles })}
          />
          <p className="note">{axisShare(config.routine_profiles.length)}</p>
        </div>

        <div className="panel">
          <h2>Horários</h2>
          <div className="field-row">
            <div className="field">
              <label>Horários diurnos</label>
              <input
                type="number"
                min={1}
                max={48}
                step={1}
                value={config.day_slots}
                onChange={(e) => patch({ day_slots: Number(e.target.value) })}
              />
            </div>
            <div className="field">
              <label>Horários noturnos</label>
              <input
                type="number"
                min={1}
                max={48}
                step={1}
                value={config.night_slots}
                onChange={(e) => patch({ night_slots: Number(e.target.value) })}
              />
            </div>
          </div>
          <p className="note">{scheduleLoad(config)}</p>
        </div>

        <div className="actions sticky-actions">
          <button className="primary" disabled={running} onClick={onRun}>
            {running
              ? `Comparando — ${runs * arms.length} simulações...`
              : arms.length === 1
                ? "Rodar modelo"
                : `Comparar ${arms.length} modelos`}
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
