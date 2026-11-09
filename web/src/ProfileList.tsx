/** Os editores dos quatro eixos de perfil.
 *
 * Dois são de **traço** e descrevem o aluno fora do mecanismo: se ele vai bem
 * na disciplina (desempenho) e quanto tempo tem (disponibilidade). Não
 * evoluem, não respondem a sinal e o aluno não os conhece. Os outros dois são
 * de **estratégia** — seletividade e concentração — e descrevem como ele pede
 * e dá lance; ver `StrategyProfileList`.
 *
 * **Não há porcentagem a editar.** A repartição entre as combinações dos dois
 * eixos é igualitária: com 3 perfis de cada lado são 9 pares e ~11% da coorte
 * em cada um. O que o usuário escolhe é quantos grupos existem; as fatias saem
 * disso.
 *
 * Os dois eixos têm editores separados porque as distribuições são de famílias
 * diferentes. O desempenho é uma normal dividida censurada em [0, 10], descrita
 * por nota média e as duas chances de ponta; a disponibilidade é uma Beta,
 * descrita por média e concentração.
 *
 * A linha selecionada é a que a prévia ao lado desenha — um perfil por vez, em
 * vez de todas as curvas sobrepostas, que com cinco ou seis grupos vira
 * emaranhado.
 */
import type { ReactNode } from "react";
import { gradeShape } from "./equations";
import type { PerformanceProfile, Profile } from "./types";

function Row({
  selected,
  onSelect,
  name,
  onName,
  removable,
  onRemove,
  children,
  warning,
}: {
  selected: boolean;
  onSelect: () => void;
  name: string;
  onName: (value: string) => void;
  removable: boolean;
  onRemove: () => void;
  children: ReactNode;
  warning?: string;
}) {
  return (
    <div
      className={`profile-row${selected ? " on" : ""}${warning ? " invalid" : ""}`}
      onClick={onSelect}
    >
      <div className="field">
        <label>Nome</label>
        <input
          type="text"
          maxLength={40}
          value={name}
          onChange={(e) => onName(e.target.value)}
          onFocus={onSelect}
        />
      </div>
      {children}
      <button
        type="button"
        className="profile-remove"
        aria-label={`Remover ${name}`}
        disabled={!removable}
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
      >
        ×
      </button>
      {warning && <p className="invalid-text">{warning}</p>}
    </div>
  );
}

function AddButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="chip" onClick={onClick}>
      + perfil
    </button>
  );
}

const nextName = (taken: string[], base: string) => {
  const used = new Set(taken);
  let suffix = taken.length + 1;
  while (used.has(`${base} ${suffix}`)) suffix += 1;
  return `${base} ${suffix}`;
};

/** As chances são editadas em **porcentagem**: 0,0005 não se digita, 0,05% se
 * lê. O `min` é a base da escada do stepper, e com passo 0,01 a grade cobre
 * tanto o 0,05% do perfil forte quanto os 3% do fraco. */
const RATE = { min: 0.01, step: 0.01, max: 99 };
const asPercent = (rate: number) => Math.round(rate * 1e6) / 1e4;

export function PerformanceProfileList({
  profiles,
  onChange,
  selected,
  onSelect,
}: {
  profiles: PerformanceProfile[];
  onChange: (profiles: PerformanceProfile[]) => void;
  selected: number;
  onSelect: (index: number) => void;
}) {
  const replace = (index: number, values: Partial<PerformanceProfile>) =>
    onChange(profiles.map((p, i) => (i === index ? { ...p, ...values } : p)));

  const add = () => {
    const last = profiles[profiles.length - 1];
    onChange([
      ...profiles,
      {
        name: nextName(
          profiles.map((p) => p.name),
          "desempenho"
        ),
        mode_grade: last?.mode_grade ?? 8,
        zero_rate: last?.zero_rate ?? 0.005,
        max_rate: last?.max_rate ?? 0.008,
      },
    ]);
    onSelect(profiles.length);
  };

  return (
    <div className="profile-list">
      {profiles.map((profile, index) => {
        // A moda é a locação, então toda nota dentro da escala tem forma. O
        // que ainda pode não fechar são as duas chances, se somarem 1 ou mais.
        const shape = gradeShape(
          profile.mode_grade,
          profile.zero_rate,
          profile.max_rate
        );
        const warning = shape
          ? undefined
          : "chances de 0 e de 10 incompatíveis";
        return (
          <Row
            key={index}
            selected={index === selected}
            onSelect={() => onSelect(index)}
            name={profile.name}
            onName={(name) => replace(index, { name })}
            removable={profiles.length > 1}
            onRemove={() => {
              onChange(profiles.filter((_, i) => i !== index));
              if (selected >= profiles.length - 1)
                onSelect(Math.max(0, profiles.length - 2));
            }}
            warning={warning}
          >
            <div className="field">
              <label>Nota mais provável</label>
              <input
                type="number"
                min={0.1}
                max={9.9}
                step={0.1}
                value={Math.round(profile.mode_grade * 10) / 10}
                onChange={(e) =>
                  replace(index, { mode_grade: Number(e.target.value) })
                }
                onFocus={() => onSelect(index)}
              />
            </div>
            <div className="field">
              <label>Chance de 0 (%)</label>
              <input
                type="number"
                min={RATE.min}
                max={RATE.max}
                step={RATE.step}
                value={asPercent(profile.zero_rate)}
                onChange={(e) =>
                  replace(index, { zero_rate: Number(e.target.value) / 100 })
                }
                onFocus={() => onSelect(index)}
              />
            </div>
            <div className="field">
              <label>Chance de 10 (%)</label>
              <input
                type="number"
                min={RATE.min}
                max={RATE.max}
                step={RATE.step}
                value={asPercent(profile.max_rate)}
                onChange={(e) =>
                  replace(index, { max_rate: Number(e.target.value) / 100 })
                }
                onFocus={() => onSelect(index)}
              />
            </div>
          </Row>
        );
      })}
      <AddButton onClick={add} />
    </div>
  );
}

/** `top` é W_a, e serve a duas coisas: é o teto da moda — acima dele não
 * existe log-normal que ainda alcance a carga máxima com a frequência pedida —
 * e é a carga contra a qual "chance de encher" se mede.
 *
 * A moda vai em horas inteiras: hora é inteira no modelo, e mostrar 28,5
 * ofereceria uma precisão que a simulação não usa. */
export function AvailabilityProfileList({
  profiles,
  onChange,
  selected,
  onSelect,
  top,
}: {
  profiles: Profile[];
  onChange: (profiles: Profile[]) => void;
  selected: number;
  onSelect: (index: number) => void;
  top: number;
}) {
  const replace = (index: number, values: Partial<Profile>) =>
    onChange(profiles.map((p, i) => (i === index ? { ...p, ...values } : p)));

  const add = () => {
    const last = profiles[profiles.length - 1];
    onChange([
      ...profiles,
      {
        name: nextName(
          profiles.map((p) => p.name),
          "disponibilidade"
        ),
        mode_hours: last?.mode_hours ?? Math.round(top * 0.8),
        full_load_rate: last?.full_load_rate ?? 0.1,
      },
    ]);
    onSelect(profiles.length);
  };

  return (
    <div className="profile-list">
      {profiles.map((profile, index) => (
        <Row
          key={index}
          selected={index === selected}
          onSelect={() => onSelect(index)}
          name={profile.name}
          onName={(name) => replace(index, { name })}
          removable={profiles.length > 1}
          onRemove={() => {
            onChange(profiles.filter((_, i) => i !== index));
            if (selected >= profiles.length - 1)
              onSelect(Math.max(0, profiles.length - 2));
          }}
          warning={
            profile.mode_hours >= top
              ? `a moda precisa ficar abaixo de ${top} h`
              : undefined
          }
        >
          <div className="field">
            <label>Moda (h)</label>
            <input
              type="number"
              min={1}
              max={top - 1}
              step={1}
              value={Math.round(profile.mode_hours)}
              onChange={(e) =>
                replace(index, { mode_hours: Number(e.target.value) })
              }
              onFocus={() => onSelect(index)}
            />
          </div>
          <div className="field">
            <label>Chance de encher (%)</label>
            <input
              type="number"
              min={RATE.min}
              max={RATE.max}
              step={RATE.step}
              value={asPercent(profile.full_load_rate)}
              onChange={(e) =>
                replace(index, { full_load_rate: Number(e.target.value) / 100 })
              }
              onFocus={() => onSelect(index)}
            />
          </div>
        </Row>
      ))}
      <AddButton onClick={add} />
    </div>
  );
}

/** Um grupo de um dos dois eixos de **estratégia** — seletividade ou
 * concentração. Os dois têm a mesma forma: um nome e um número. */
interface StrategyProfile {
  name: string;
  value: number;
}

/** O editor dos eixos de estratégia. Um só componente para os dois porque a
 * linha é a mesma — nome e valor —, e o que muda é o intervalo aceito e o
 * rótulo do campo. Não há prévia ao lado: o valor não descreve distribuição
 * nenhuma, e sim uma regra de decisão, então não há curva a desenhar.
 *
 * Sem seleção de linha, pelo mesmo motivo — a linha selecionada só serve para
 * dizer qual curva a prévia mostra. */
export function StrategyProfileList<T extends StrategyProfile>({
  profiles,
  onChange,
  label,
  base,
  min,
  max,
  step,
  fallback,
}: {
  profiles: T[];
  onChange: (profiles: T[]) => void;
  label: string;
  /** Prefixo do nome proposto a um perfil novo. */
  base: string;
  min: number;
  max?: number;
  step: number;
  /** Valor do primeiro perfil, se a lista estiver vazia. */
  fallback: number;
}) {
  const replace = (index: number, values: Partial<StrategyProfile>) =>
    onChange(profiles.map((p, i) => (i === index ? { ...p, ...values } : p)));

  const add = () => {
    const last = profiles[profiles.length - 1];
    onChange([
      ...profiles,
      {
        name: nextName(
          profiles.map((p) => p.name),
          base
        ),
        value: last?.value ?? fallback,
      } as T,
    ]);
  };

  // O nome é rótulo de relatório e precisa ser único dentro do eixo: dois
  // grupos com o mesmo nome se fundiriam no recorte por perfil.
  const counts = new Map<string, number>();
  for (const p of profiles) counts.set(p.name, (counts.get(p.name) ?? 0) + 1);

  const range =
    max === undefined ? `pelo menos ${min}` : `entre ${min} e ${max}`;

  return (
    <div className="profile-list">
      {profiles.map((profile, index) => {
        const outOfRange =
          !Number.isFinite(profile.value) ||
          profile.value < min ||
          (max !== undefined && profile.value > max);
        const warning = !profile.name.trim()
          ? "o nome não pode ficar vazio"
          : (counts.get(profile.name) ?? 0) > 1
            ? "nome repetido neste eixo"
            : outOfRange
              ? `o valor deve ser ${range}`
              : undefined;
        return (
          <Row
            key={index}
            selected={false}
            onSelect={() => {}}
            name={profile.name}
            onName={(name) => replace(index, { name })}
            removable={profiles.length > 1}
            onRemove={() => onChange(profiles.filter((_, i) => i !== index))}
            warning={warning}
          >
            <div className="field">
              <label>{label}</label>
              <input
                type="number"
                min={min}
                max={max}
                step={step}
                value={profile.value}
                onChange={(e) =>
                  replace(index, { value: Number(e.target.value) })
                }
              />
            </div>
          </Row>
        );
      })}
      <AddButton onClick={add} />
    </div>
  );
}

/** O rodapé de uma das duas seções.
 *
 * A fatia é a **deste eixo**, não a da combinação: o que a lista acima edita
 * são os grupos de desempenho *ou* os de disponibilidade, e dizer 11% ali
 * responderia a uma pergunta que a seção não faz.
 */
export const axisShare = (profiles: number): string => {
  const share = profiles > 0 ? 100 / profiles : 0;
  const pct = share.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  return `${profiles} ${profiles === 1 ? "perfil" : "perfis"} · ${pct}% da coorte em cada`;
};
