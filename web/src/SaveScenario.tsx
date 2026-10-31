/** O controle de salvar o cenário atual, ao lado do botão de comparar.
 *
 * Abre em dois tempos: o botão revela o campo do nome, e só o segundo clique
 * (ou Enter) grava. Sem isso, salvar seria um clique irreversível que cria uma
 * entrada com nome genérico — e a lista encheria de "Cenário 1", "Cenário 2".
 *
 * Esc cancela e devolve o foco ao botão, que é o que se espera de um campo que
 * apareceu por cima de uma barra de ações.
 */
import { useEffect, useRef, useState } from "react";

export function SaveScenario({
  onSave,
  suggestion,
  exists,
}: {
  onSave: (name: string) => void;
  /** Nome proposto no campo, já selecionado — digitar por cima é mais rápido
   * que apagar. */
  suggestion: string;
  /** Se já há um cenário salvo com este nome. O nome é a identidade, então
   * salvar por cima **substitui** — e o botão diz isso antes do clique, em vez
   * de o usuário descobrir depois. */
  exists: (name: string) => boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(suggestion);
  const field = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (editing) field.current?.select();
  }, [editing]);

  const open = () => {
    setName(suggestion);
    setEditing(true);
  };

  const close = () => {
    setEditing(false);
    trigger.current?.focus();
  };

  const confirm = () => {
    if (!name.trim()) return;
    onSave(name);
    setEditing(false);
  };

  if (!editing) {
    return (
      <button ref={trigger} type="button" className="secondary" onClick={open}>
        Salvar cenário
      </button>
    );
  }

  return (
    <div className="save-scenario">
      <input
        ref={field}
        type="text"
        maxLength={60}
        value={name}
        aria-label="Nome do cenário"
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") confirm();
          if (e.key === "Escape") close();
        }}
      />
      <button type="button" className="secondary" disabled={!name.trim()} onClick={confirm}>
        {name.trim() && exists(name) ? "Substituir" : "Salvar"}
      </button>
      <button
        type="button"
        className="save-cancel"
        aria-label="Cancelar"
        title="Cancelar"
        onClick={close}
      >
        ×
      </button>
    </div>
  );
}
