import { useEffect, useMemo, useState } from "react";
import { trace } from "./api";
import { formatRatio } from "./charts";
import type { ComparisonRun } from "./history";
import { COMPARISON_ARMS, GUARANTEED_ROUND, armLabel, cohortLabel } from "./types";
import type {
  DisciplineSnapshot,
  RequestRecord,
  StudentHistory,
  StudentPeriodRecord,
  StudentSummary,
  TraceResponse,
} from "./types";

/** A utilidade é uma fração que soma 1 na linha do aluno, então ela vive na
 * terceira casa: com duas, as disciplinas de uma grade grande empatam todas. */
const formatUtility = (value: number) =>
  value.toLocaleString("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 });

/** O que aconteceu com uma linha **naquela rodada**.
 *
 * São as quatro saídas que a tela colore, e a cor nunca anda sozinha: a
 * palavra está na célula, porque o amarelo não alcança 3:1 sobre o fundo claro
 * (ver a paleta de estado em `charts/theme.ts`).
 *
 * `idle` é o cinza, e leva duas palavras diferentes. **Não solicitada** é a
 * disciplina elegível que não recebeu lance na rodada — ou o aluno não quis,
 * ou ela saiu de B_a^(t,r) antes (sem vaga, sem carga ou sem orçamento), e é o
 * caso que costuma explicar um resultado inesperado. **Já obtida** é a que ele
 * ganhou numa rodada anterior: ela não está mais em disputa, e chamá-la de não
 * solicitada esconderia justamente o que deu certo. */
type Tone = "approved" | "failed" | "refused" | "idle";

interface Outcome {
  label: string;
  tone: Tone;
  /** A vaga que não veio de rodada nenhuma: a matrícula garantida do
   * ingressante, concedida antes de o leilão abrir. */
  guaranteed: boolean;
}

function outcomeOf(record: RequestRecord, round: number): Outcome {
  const won = record.won_round;
  const guaranteed = won === GUARANTEED_ROUND;
  // A garantida é creditada na 1ª rodada: é ali que ela passa a valer, e é
  // assim que a simulação a conta (ver `simulation.rounds`).
  const settled = won !== null && (won === round || (guaranteed && round === 1));
  if (settled) {
    return record.approved
      ? { label: "aprovada", tone: "approved", guaranteed }
      : { label: "reprovada", tone: "failed", guaranteed };
  }
  if (record.bids[round - 1] > 0) return { label: "recusada", tone: "refused", guaranteed: false };
  if (won !== null && (guaranteed || won < round)) {
    return { label: "já obtida", tone: "idle", guaranteed };
  }
  return { label: "não solicitada", tone: "idle", guaranteed: false };
}

/** Quem vale a pena ver nesta rodada quando as cinzas estão escondidas. */
const isLive = (outcome: Outcome) => outcome.tone !== "idle";

const Chip = ({ outcome }: { outcome: Outcome }) => (
  <span className={`outcome ${outcome.tone}`}>{outcome.label}</span>
);

/** O rótulo da coluna de crédito muda com o mecanismo: na linha de base não há
 * lance, e o registro guarda só a marca de que houve pedido. */
const bidCell = (credits: number, usesCredits: boolean) =>
  usesCredits ? (credits || "—") : credits > 0 ? "pedida" : "—";

export function Trace({ run }: { run: ComparisonRun }) {
  const result = run.result;
  /** Só os braços que esta comparação de fato rodou: uma gravada antes de um
   * braço existir não o traz, e pedir o traço dele não encontraria execução. */
  const arms = useMemo(
    () => COMPARISON_ARMS.filter((arm) => result.arms.some((a) => a.key === arm.key)),
    [result.arms]
  );

  // O padrão é o último braço do caminho — o modelo proposto, e o único em que
  // todas as colunas de crédito têm o que mostrar.
  const [armKey, setArmKey] = useState(arms[arms.length - 1]?.key ?? COMPARISON_ARMS[0].key);
  const [seed, setSeed] = useState(1);
  /** O traço custa uma simulação completa no servidor, então ele não vem
   * sozinho: a seção abre com o botão, e dali em diante trocar de modelo ou de
   * execução já refaz. */
  const [started, setStarted] = useState(false);
  /** Contador de tentativas: é o que dá ao botão "tentar de novo" o que mudar
   * quando o par (braço, seed) continua o mesmo. */
  const [attempt, setAttempt] = useState(0);
  const [data, setData] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [kind, setKind] = useState<"student" | "discipline">("student");
  const [studentId, setStudentId] = useState<string | null>(null);
  const [discipline, setDiscipline] = useState<string | null>(null);
  const [showIdle, setShowIdle] = useState(true);

  useEffect(() => {
    if (!started) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    // `runs` é da comparação, não do cenário: o que o traço pede é uma
    // execução só, endereçada pelo par (braço, seed).
    const { runs: _runs, ...scenario } = run.config;
    trace({ ...scenario, arm: armKey, seed })
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setError(e.message);
          setData(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [started, attempt, armKey, seed, run.config]);

  /** O mecanismo do braço **carregado**, e não o do seletor: as colunas de
   * crédito descrevem o que está na tela, e trocar de modelo só as troca
   * quando o traço novo chega. */
  const loadedArm = data ? result.arms.find((arm) => arm.key === data.arm) : undefined;
  const usesCredits = loadedArm ? loadedArm.mechanism === "credits" : true;
  const hasReturn = loadedArm ? loadedArm.credit_return !== "none" : false;
  const rounds = run.config.rounds;

  /** O sujeito sai do que está carregado: se o escolhido não existe mais —
   * primeira abertura, ou troca de cenário —, cai no primeiro da lista em vez
   * de deixar a tela vazia. */
  const student =
    data?.students.find((s) => s.id === studentId) ?? data?.students[0] ?? null;
  const chosen =
    data?.disciplines.find((name) => name === discipline) ?? data?.disciplines[0] ?? null;

  return (
    <section className="chart-section">
      <header className="chart-section-head">
        <h2>Histórico de um aluno ou de uma disciplina</h2>
        <p>
          O caso individual por trás dos agregados: uma execução, período a período e
          rodada a rodada. O par (modelo, execução) endereça um dos pontos dos boxplots, e
          a simulação é refeita no servidor — determinística, então é a mesma de que o
          ponto saiu. A vista por aluno lista todas as disciplinas elegíveis dele, inclusive
          as que não pediu; a por disciplina lista quem a pediu naquela rodada.
        </p>
      </header>

      <div className="panel trace-controls">
        <div className="field-row">
          <div className="field">
            <label htmlFor="trace-arm">Modelo</label>
            <select
              id="trace-arm"
              value={armKey}
              onChange={(event) => setArmKey(event.target.value)}
            >
              {arms.map((arm) => (
                <option key={arm.key} value={arm.key}>
                  {arm.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="trace-seed">Execução (seed)</label>
            <select
              id="trace-seed"
              value={seed}
              onChange={(event) => setSeed(Number(event.target.value))}
            >
              {Array.from({ length: result.runs }, (_, i) => i + 1).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>

          {data && (
            <>
              <div className="field">
                <label>O que ver</label>
                <div className="view-switch">
                  <button
                    type="button"
                    className={kind === "student" ? "on" : ""}
                    onClick={() => setKind("student")}
                  >
                    Aluno
                  </button>
                  <button
                    type="button"
                    className={kind === "discipline" ? "on" : ""}
                    onClick={() => setKind("discipline")}
                  >
                    Disciplina
                  </button>
                </div>
              </div>

              {kind === "student" ? (
                <div className="field grow">
                  <label htmlFor="trace-student">Aluno</label>
                  <select
                    id="trace-student"
                    value={student?.id ?? ""}
                    onChange={(event) => setStudentId(event.target.value)}
                  >
                    {cohortsOf(data.students).map(([cohort, people]) => (
                      <optgroup key={cohort} label={cohortLabel(cohort)}>
                        {people.map((person) => (
                          <option key={person.id} value={person.id}>
                            {person.name}
                            {person.graduated_at === null
                              ? ""
                              : ` — formou no período ${person.graduated_at}`}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="field grow">
                  <label htmlFor="trace-discipline">Disciplina</label>
                  <select
                    id="trace-discipline"
                    value={chosen ?? ""}
                    onChange={(event) => setDiscipline(event.target.value)}
                  >
                    {groupDisciplines(data, run.config.disciplines).map(([group, names]) => (
                      <optgroup key={group} label={group}>
                        {names.map((name) => (
                          <option key={name} value={name}>
                            {name}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>
              )}

              {kind === "student" && (
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={showIdle}
                    onChange={(event) => setShowIdle(event.target.checked)}
                  />
                  mostrar não solicitadas
                </label>
              )}
            </>
          )}

          {!data && !loading && (
            <button
              type="button"
              onClick={() => (started ? setAttempt((n) => n + 1) : setStarted(true))}
            >
              {started ? "Tentar de novo" : "Abrir histórico"}
            </button>
          )}
        </div>

        {/* A legenda é a mitigação prevista para a paleta de estado: a cor diz
            de relance, a palavra diz o que ela quer dizer. */}
        {data && (
          <p className="note trace-legend">
            Em cada rodada:{" "}
            <Chip outcome={{ label: "aprovada", tone: "approved", guaranteed: false }} /> cursou e
            passou ·{" "}
            <Chip outcome={{ label: "reprovada", tone: "failed", guaranteed: false }} /> cursou e
            não passou ·{" "}
            <Chip outcome={{ label: "recusada", tone: "refused", guaranteed: false }} /> pediu e
            não obteve ·{" "}
            <Chip outcome={{ label: "não solicitada", tone: "idle", guaranteed: false }} /> elegível
            e sem pedido, ou já obtida antes. A nota é do fim do período, e só existe onde
            houve vaga.
          </p>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {loading && (
        <p className="empty-state">
          Refazendo a execução {seed} de {armLabel(armKey)} — é uma simulação completa.
        </p>
      )}

      {data && !loading && kind === "student" && student && (
        <StudentTrace
          data={data}
          student={student}
          rounds={rounds}
          usesCredits={usesCredits}
          hasReturn={hasReturn}
          showIdle={showIdle}
        />
      )}
      {data && !loading && kind === "discipline" && chosen && (
        <DisciplineTrace
          data={data}
          discipline={chosen}
          rounds={rounds}
          usesCredits={usesCredits}
        />
      )}
    </section>
  );
}

/** Os alunos por geração, na ordem do ingresso — como o seletor os agrupa. */
function cohortsOf(students: StudentSummary[]): [number, StudentSummary[]][] {
  const groups = new Map<number, StudentSummary[]>();
  for (const student of students) {
    const list = groups.get(student.entry_period) ?? [];
    list.push(student);
    groups.set(student.entry_period, list);
  }
  return [...groups.entries()].sort((a, b) => a[0] - b[0]);
}

/** As disciplinas por período da grade, com as optativas num grupo à parte.
 *
 * A optativa não tem período a mostrar: ela não tem pré-requisito, então a
 * indução a colocaria no 1º, onde ela não está. Quem sabe que ela é optativa é
 * o cenário, e é de lá que vem a separação. */
function groupDisciplines(
  data: TraceResponse,
  configured: { name: string; elective?: boolean }[]
): [string, string[]][] {
  const elective = new Set(configured.filter((d) => d.elective).map((d) => d.name));
  const groups = new Map<number, string[]>();
  const electives: string[] = [];
  for (const name of data.disciplines) {
    if (elective.has(name)) {
      electives.push(name);
      continue;
    }
    const period = data.curriculum_periods[name] ?? 0;
    const list = groups.get(period) ?? [];
    list.push(name);
    groups.set(period, list);
  }
  const ordered: [string, string[]][] = [...groups.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([period, names]) => [`Período ${period} da grade`, names]);
  return electives.length ? [...ordered, ["Optativas", electives]] : ordered;
}

function StudentTrace({
  data,
  student,
  rounds,
  usesCredits,
  hasReturn,
  showIdle,
}: {
  data: TraceResponse;
  student: StudentSummary;
  rounds: number;
  usesCredits: boolean;
  hasReturn: boolean;
  showIdle: boolean;
}) {
  const history: StudentHistory | undefined = useMemo(
    () => data.histories.find((entry) => entry.student_id === student.id),
    [data, student.id]
  );
  const records = history?.periods ?? [];

  return (
    <>
      <div className="panel student-head">
        <div>
          <h3>{student.name}</h3>
          <p className="note">
            {cohortLabel(student.entry_period)} · {student.id}
          </p>
        </div>
        <dl className="stat-row">
          <div>
            <dt>Ingresso</dt>
            <dd>{`período ${student.entry_period}`}</dd>
          </div>
          <div>
            <dt>CR</dt>
            <dd>{formatRatio(student.grade_average)}</dd>
          </div>
          <div>
            <dt>Horas aprovadas</dt>
            <dd>
              {student.approved_hours} / {student.hours_to_graduate}
            </dd>
          </div>
          <div>
            <dt>Matrículas</dt>
            <dd>{student.enrollments}</dd>
          </div>
          <div>
            <dt>Aprovações</dt>
            <dd>{student.approvals}</dd>
          </div>
          <div>
            <dt>Satisfação média</dt>
            <dd>{formatRatio(student.mean_satisfaction)}</dd>
          </div>
          <div>
            <dt>Conclusão</dt>
            <dd>{student.graduated_at ? `período ${student.graduated_at}` : "em curso"}</dd>
          </div>
        </dl>
      </div>

      {records.length === 0 ? (
        <div className="panel">
          <p className="empty-state">
            Este aluno não participou de nenhuma matrícula: ingressou no período{" "}
            {student.entry_period}, depois do fim do horizonte simulado.
          </p>
        </div>
      ) : (
        records.map((record) => (
          <StudentPeriod
            key={record.period}
            record={record}
            rounds={rounds}
            usesCredits={usesCredits}
            hasReturn={hasReturn}
            showIdle={showIdle}
          />
        ))
      )}
    </>
  );
}

function StudentPeriod({
  record,
  rounds,
  usesCredits,
  hasReturn,
  showIdle,
}: {
  record: StudentPeriodRecord;
  rounds: number;
  usesCredits: boolean;
  hasReturn: boolean;
  showIdle: boolean;
}) {
  const won = record.requests.filter((request) => request.won_round !== null).length;
  const asked = record.requests.filter((request) => request.bids.some((c) => c > 0)).length;
  // No período de ingresso não houve disputa: as vagas vieram garantidas, e
  // "6 de 6 pedidos atendidos" leria como um leilão bem-sucedido.
  const guaranteed = record.requests.some(
    (request) => request.won_round === GUARANTEED_ROUND
  );

  return (
    <article className="panel period-panel">
      <header className="period-summary-row">
        <h3>
          {`Período ${record.period}`}
          {guaranteed && <span className="badge">matrícula garantida</span>}
          {record.graduated && <span className="badge">concluiu o curso</span>}
        </h3>
        <span className="period-summary">
          {won} de {asked} pedidos atendidos · {record.enrolled_hours} h · ψ{" "}
          {formatRatio(record.satisfaction)} · CR {formatRatio(record.grade_average)}
          {usesCredits &&
            ` · créditos ${record.credits_start} − ${record.credits_spent} → ${record.credits_end}`}
          {usesCredits && hasReturn && ` · retorno γ ${record.credits_returned}`}
        </span>
      </header>

      {Array.from({ length: rounds }, (_, index) => index + 1).map((round) => {
        const rows = record.requests
          .map((request) => ({ request, outcome: outcomeOf(request, round) }))
          .filter((row) => showIdle || isLive(row.outcome));
        return (
          <div className="round-block" key={round}>
            <h4 className="round-head">
              Rodada {round}
              <span className="round-count">
                {rows.length === 1 ? "1 disciplina" : `${rows.length} disciplinas`}
              </span>
            </h4>
            {rows.length === 0 ? (
              <p className="empty-state">Nenhum pedido nesta rodada.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Disciplina</th>
                    <th>Utilidade</th>
                    <th>{usesCredits ? "Lance" : "Solicitação"}</th>
                    <th>Resultado</th>
                    <th>Nota</th>
                    {usesCredits && <th>Pago</th>}
                    {hasReturn && <th>Retorno γ</th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ request, outcome }) => {
                    // Nota, pagamento e retorno são do par (aluno, disciplina)
                    // no período, e pertencem à rodada em que a vaga saiu: nas
                    // outras eles ainda não existiam.
                    const settled = outcome.tone === "approved" || outcome.tone === "failed";
                    return (
                      <tr key={request.discipline} className={outcome.tone === "idle" ? "idle-row" : undefined}>
                        <td>{request.discipline}</td>
                        <td>{formatUtility(request.utility)}</td>
                        <td>{bidCell(request.bids[round - 1] ?? 0, usesCredits)}</td>
                        <td>
                          <Chip outcome={outcome} />
                          {outcome.guaranteed && (
                            <span className="outcome-note">vaga garantida</span>
                          )}
                        </td>
                        <td className={settled ? outcome.tone : undefined}>
                          {settled && request.grade !== null
                            ? `${formatRatio(request.grade)}${
                                request.attempt && request.attempt > 1
                                  ? ` (${request.attempt}ª tentativa)`
                                  : ""
                              }`
                            : "—"}
                        </td>
                        {usesCredits && <td>{settled ? request.paid : "—"}</td>}
                        {hasReturn && <td>{settled ? request.returned : "—"}</td>}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </article>
  );
}

/** Uma linha da vista por disciplina: o aluno que a pediu naquele período. */
interface Bidder {
  student: StudentSummary;
  request: RequestRecord;
  /** O CR com que ele entrou no período — a prioridade da linha de base. */
  cr: number;
}

function DisciplineTrace({
  data,
  discipline,
  rounds,
  usesCredits,
}: {
  data: TraceResponse;
  discipline: string;
  rounds: number;
  usesCredits: boolean;
}) {
  /** Quem pediu esta disciplina, período a período. O índice é montado uma vez
   * por disciplina escolhida: varrer os históricos a cada rodada seria varrer
   * a população inteira |T| × |R| vezes. */
  const byPeriod = useMemo(() => {
    const students = new Map(data.students.map((student) => [student.id, student]));
    const index = new Map<number, Bidder[]>();
    for (const history of data.histories) {
      const student = students.get(history.student_id);
      if (!student) continue;
      for (const period of history.periods) {
        const request = period.requests.find((entry) => entry.discipline === discipline);
        if (!request) continue;
        const list = index.get(period.period) ?? [];
        list.push({ student, request, cr: period.grade_average });
        index.set(period.period, list);
      }
    }
    return index;
  }, [data, discipline]);

  const offers = useMemo(() => {
    const map = new Map<number, DisciplineSnapshot>();
    for (const period of data.periods) {
      const snapshot = period.disciplines.find((entry) => entry.name === discipline);
      if (snapshot) map.set(period.period, snapshot);
    }
    return map;
  }, [data, discipline]);

  const first = data.periods[0]?.disciplines.find((entry) => entry.name === discipline);

  return (
    <>
      <div className="panel student-head">
        <div>
          <h3>{discipline}</h3>
          <p className="note">
            {first
              ? `${first.hours} h · ${first.seats} vagas · período ${first.curriculum_period} da grade`
              : "fora da oferta desta execução"}
          </p>
        </div>
      </div>

      {data.periods.map((period) => {
        const offer = offers.get(period.period);
        const bidders = byPeriod.get(period.period) ?? [];
        return (
          <article className="panel period-panel" key={period.period}>
            <header className="period-summary-row">
              <h3>{`Período ${period.period}`}</h3>
              {offer && (
                <span className="period-summary">
                  {offer.filled} de {offer.seats} vagas preenchidas
                  {offer.granted > 0 && ` (${offer.granted} garantidas)`} · {offer.requests}{" "}
                  solicitantes
                  {usesCredits &&
                    offer.mean_price !== null &&
                    ` · preço médio π ${formatRatio(offer.mean_price)}`}{" "}
                  · {offer.approvals} aprovações
                </span>
              )}
            </header>

            {Array.from({ length: rounds }, (_, index) => index + 1).map((round) => {
              // Só quem pediu **nesta** rodada: a vista por disciplina não tem
              // não solicitadas, senão toda linha seria a população inteira.
              const rows = bidders
                .map((bidder) => ({ ...bidder, outcome: outcomeOf(bidder.request, round) }))
                .filter(
                  ({ request, outcome }) =>
                    request.bids[round - 1] > 0 ||
                    outcome.tone === "approved" ||
                    outcome.tone === "failed"
                )
                // Na ordem em que o mecanismo as olhou: pelo lance, e pelo CR
                // onde não há lance que os separe.
                .sort(
                  (a, b) =>
                    (b.request.bids[round - 1] ?? 0) - (a.request.bids[round - 1] ?? 0) ||
                    b.cr - a.cr
                );
              return (
                <div className="round-block" key={round}>
                  <h4 className="round-head">
                    Rodada {round}
                    <span className="round-count">
                      {rows.length === 1 ? "1 pedido" : `${rows.length} pedidos`}
                    </span>
                  </h4>
                  {rows.length === 0 ? (
                    <p className="empty-state">Ninguém pediu esta disciplina nesta rodada.</p>
                  ) : (
                    <table>
                      <thead>
                        <tr>
                          <th>Aluno</th>
                          <th>Geração</th>
                          <th>CR</th>
                          <th>Utilidade</th>
                          {usesCredits && <th>Lance</th>}
                          <th>Resultado</th>
                          <th>Nota</th>
                          {usesCredits && <th>Pago</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map(({ student, request, cr, outcome }) => {
                          const settled =
                            outcome.tone === "approved" || outcome.tone === "failed";
                          return (
                            <tr key={student.id}>
                              <td>{student.name}</td>
                              <td className="muted-cell">{student.entry_period}</td>
                              <td>{formatRatio(cr)}</td>
                              <td>{formatUtility(request.utility)}</td>
                              {usesCredits && <td>{request.bids[round - 1] || "—"}</td>}
                              <td>
                                <Chip outcome={outcome} />
                                {outcome.guaranteed && (
                                  <span className="outcome-note">vaga garantida</span>
                                )}
                              </td>
                              <td className={settled ? outcome.tone : undefined}>
                                {settled && request.grade !== null
                                  ? formatRatio(request.grade)
                                  : "—"}
                              </td>
                              {usesCredits && <td>{settled ? request.paid : "—"}</td>}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>
              );
            })}
          </article>
        );
      })}
    </>
  );
}
