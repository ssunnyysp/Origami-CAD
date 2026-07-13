import type { FlasherGeometry } from "../../model/types";
import { useAppStore } from "../../store/useAppStore";
import { ModelSelector } from "./ModelSelector";
import { FoldnessSlider } from "./FoldnessSlider";
import { AnimateToggle } from "./AnimateToggle";
import { ColorPicker } from "./ColorPicker";
import { FoldImportExport } from "./FoldImportExport";

interface Props {
  geometry: FlasherGeometry | null;
}

// Grouped into labeled sections (rather than one flat list of rows) so the
// panel reads as "model, then fold, then appearance, then file I/O" instead
// of an undifferentiated form — related controls are visually near each
// other and unrelated ones are separated by a rule + label.
export function ControlPanel({ geometry }: Props) {
  const viewMode = useAppStore((s) => s.viewMode);
  const setViewMode = useAppStore((s) => s.setViewMode);
  const showingPattern = viewMode === "pattern";

  return (
    <div className="pane-controls">
      <section className="panel-section panel-section--first">
        <h2 className="section-label">Model</h2>
        <ModelSelector />
      </section>

      <section className="panel-section">
        <h2 className="section-label">Fold</h2>
        <FoldnessSlider />
        <AnimateToggle />
      </section>

      <section className="panel-section">
        <h2 className="section-label">Appearance</h2>
        <ColorPicker />
        <button
          className="action-button action-button--secondary"
          onClick={() => setViewMode(showingPattern ? "3d" : "pattern")}
        >
          {showingPattern ? "View 3D model" : "View crease pattern"}
        </button>
      </section>

      <section className="panel-section">
        <h2 className="section-label">FOLD file</h2>
        <FoldImportExport geometry={geometry} />
      </section>
    </div>
  );
}
