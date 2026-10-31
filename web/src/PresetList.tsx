import { PRESETS } from "./presets";
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
  /** Se há um cenário próprio guardado para voltar. */
  hasCustom: boolean;
  /** Os cenários que o usuário salvou no navegador, do mais recente ao mais
   * antigo. Dividem o endereçamento com os prontos: um id é um id. */
  saved: SavedPreset[];
  onSelect: (presetId: string | null) => void;
  onDelete: (presetId: string) => void;
}) {
  return (
    <aside className="rail" aria-label="Presets">
      <div className="rail-head">
        <h2>Presets</h2>
        <p className="rail-count">Cenários prontos — clique para carregar.</p>
      </div>

      <ul className="rail-list">
        <li>
          <button
            className={`rail-item ${selected === null ? "current" : ""}`}
            onClick={() => onSelect(null)}
            disabled={selected === null || !hasCustom}
          >
            <span className="rail-item-name">Personalizado</span>
            <span className="rail-item-hint">
              {selected === null
                ? "O cenário que você montou."
                : hasCustom
                  ? "Volta ao cenário que você montou."
                  : "Qualquer alteração no formulário vem parar aqui."}
            </span>
          </button>
        </li>

        {PRESETS.map((preset) => (
          <li key={preset.id}>
            <button
              className={`rail-item ${selected === preset.id ? "current" : ""}`}
              onClick={() => onSelect(preset.id)}
              disabled={selected === preset.id}
            >
              <span className="rail-item-name">{preset.name}</span>
              <span className="rail-item-hint">{preset.hint}</span>
            </button>
          </li>
        ))}

        {saved.length > 0 && (
          <li className="rail-section" aria-hidden="true">
            Salvos
          </li>
        )}

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
