/** O editor de um dos dois eixos de perfil.
 *
 * O perfil descreve o comportamento do aluno **fora do mecanismo**: se ele vai
 * bem na disciplina (desempenho) ou se a larga (disponibilidade). É traço
 * imutável — não evolui, não responde a sinal e o aluno não o conhece.
 *
 * **Não há porcentagem a editar.** A repartição entre as combinações dos dois
 * eixos é igualitária: com 3 perfis de cada lado são 9 pares e ~11% da geração
 * em cada um. O que o usuário escolhe é quantos grupos existem; as fatias saem
 * disso.
 *
 * A linha selecionada é a que a prévia ao lado desenha — um perfil por vez, em
 * vez de todas as curvas sobrepostas, que com cinco ou seis grupos vira
 * emaranhado.
 */
import type { Profile } from "./types";

/** Como a média deste eixo se edita.
 *
 * `grade` mostra a média da aptidão como **nota** (o mesmo número vezes 10):
 * em dificuldade 1 e primeira tentativa a nota *é* a aptidão, então é assim
 * que ela se lê. `fraction` mostra a disponibilidade como ela é, uma fração
 * de W_a. */
export type MeanScale = "grade" | "fraction";

const SCALES = {
  grade: { factor: 10, min: 0.1, max: 9.9, step: 0.1, label: "Nota média" },
  fraction: { factor: 1, min: 0.01, max: 0.99, step: 0.01, label: "Fração média" },
} as const;

export function ProfileList({
  profiles,
  onChange,
  selected,
  onSelect,
  scale,
  newName,
}: {
  profiles: Profile[];
  onChange: (profiles: Profile[]) => void;
  selected: number;
  onSelect: (index: number) => void;
  scale: MeanScale;
  /** Nome do perfil criado pelo botão, numerado para não colidir. */
  newName: string;
}) {
  const ruler = SCALES[scale];

  const replace = (index: number, values: Partial<Profile>) =>
    onChange(profiles.map((p, i) => (i === index ? { ...p, ...values } : p)));

  const add = () => {
    const taken = new Set(profiles.map((p) => p.name));
    let suffix = profiles.length + 1;
    while (taken.has(`${newName} ${suffix}`)) suffix += 1;
    const last = profiles[profiles.length - 1];
    onChange([
      ...profiles,
      {
        name: `${newName} ${suffix}`,
        mean: last?.mean ?? 0.65,
        concentration: last?.concentration ?? 10,
      },
    ]);
    onSelect(profiles.length);
  };

  const remove = (index: number) => {
    onChange(profiles.filter((_, i) => i !== index));
    if (selected >= profiles.length - 1) onSelect(Math.max(0, profiles.length - 2));
  };

  return (
    <div className="profile-list">
      {profiles.map((profile, index) => (
        <div
          key={index}
          className={`profile-row${index === selected ? " on" : ""}`}
          onClick={() => onSelect(index)}
        >
          <div className="field">
            <label>Nome</label>
            <input
              type="text"
              maxLength={40}
              value={profile.name}
              onChange={(e) => replace(index, { name: e.target.value })}
              onFocus={() => onSelect(index)}
            />
          </div>
          <div className="field">
            <label>{ruler.label}</label>
            {/* O arredondamento no caminho de ida evita que 0,67 apareça como
                6,700000000000001. */}
            <input
              type="number"
              min={ruler.min}
              max={ruler.max}
              step={ruler.step}
              value={Math.round(profile.mean * ruler.factor * 1000) / 1000}
              onChange={(e) =>
                replace(index, { mean: Number(e.target.value) / ruler.factor })
              }
              onFocus={() => onSelect(index)}
            />
          </div>
          <div className="field">
            <label>Concentração</label>
            <input
              type="number"
              min={0.5}
              step={0.5}
              value={profile.concentration}
              onChange={(e) =>
                replace(index, { concentration: Number(e.target.value) })
              }
              onFocus={() => onSelect(index)}
            />
          </div>
          <button
            type="button"
            className="profile-remove"
            aria-label={`Remover ${profile.name}`}
            disabled={profiles.length < 2}
            onClick={(e) => {
              e.stopPropagation();
              remove(index);
            }}
          >
            ×
          </button>
        </div>
      ))}
      <button type="button" className="chip" onClick={add}>
        + perfil
      </button>
    </div>
  );
}

/** O rodapé de uma das duas seções.
 *
 * A fatia é a **deste eixo**, não a da combinação: o que a lista acima edita
 * são os grupos de desempenho *ou* os de disponibilidade, e dizer 11% ali
 * responderia a uma pergunta que a seção não faz. A contagem de combinações
 * vem depois, nomeando o outro eixo como o que ela é — consequência de
 * multiplicar os dois.
 */
export const axisShare = (profiles: number, other: number): string => {
  const share = profiles > 0 ? 100 / profiles : 0;
  const pairs = Math.max(1, profiles * other);
  const pct = share.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  return (
    `${profiles} ${profiles === 1 ? "perfil" : "perfis"} · ${pct}% da geração ` +
    `em cada · ${pairs} ${pairs === 1 ? "combinação" : "combinações"} com o outro eixo`
  );
};
