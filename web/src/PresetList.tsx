import { describeSaved } from "./savedPresets";
import type { SavedPreset } from "./savedPresets";

export function PresetList({
  selected,
  hasCustom,
  saved,
  onSelect,
  onDelete,
}: {
  /** Preset carregado no formulário; `null` = o cenário montado à mão. */
  selected: string | null;
  /** Se há um cenário próprio guardado para voltar. Sem ele, "Personalizado"
   * devolve os valores padrão. */
  hasCustom: boolean;
  /** Os cenários que o usuário salvou no navegador, do mais recente ao mais
   * antigo. São os únicos que existem: não há lista fixa. */
  saved: SavedPreset[];
  onSelect: (presetId: string | null) => void;
  onDelete: (presetId: string) => void;
}) {
  return (
    <aside className="rail" aria-label="Cenários">
      <div className="rail-head">
        <h2>Cenários</h2>
        <p className="rail-count">
          {saved.length > 0
            ? "Salvos no navegador — clique para carregar."
            : "Salve um cenário para ele aparecer aqui."}
        </p>
      </div>

      <ul className="rail-list">
        <li>
          <button
            className={`rail-item ${selected === null ? "current" : ""}`}
            onClick={() => onSelect(null)}
            disabled={selected === null}
          >
            <span className="rail-item-name">Personalizado</span>
            <span className="rail-item-hint">
              {selected === null
                ? hasCustom
                  ? "O cenário que você montou."
                  : "Os valores padrão."
                : hasCustom
                  ? "Volta ao cenário que você montou."
                  : "Volta aos valores padrão."}
            </span>
          </button>
        </li>

        {saved.map((preset) => (
          <li key={preset.id} className="rail-row">
            <button
              className={`rail-item ${selected === preset.id ? "current" : ""}`}
              onClick={() => onSelect(preset.id)}
              disabled={selected === preset.id}
            >
              <span className="rail-item-name">{preset.name}</span>
              <span className="rail-item-hint">{describeSaved(preset)}</span>
            </button>
            <button
              className="nav-delete"
              onClick={() => onDelete(preset.id)}
              title={`Apagar o cenário "${preset.name}"`}
              aria-label={`Apagar o cenário "${preset.name}"`}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
