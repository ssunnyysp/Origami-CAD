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

export function ControlPanel({ geometry }: Props) {
  const viewMode = useAppStore((s) => s.viewMode);
  const setViewMode = useAppStore((s) => s.setViewMode);
  const showingPattern = viewMode === "pattern";

  return (
    <div className="pane-controls">
      <ModelSelector />
      <FoldnessSlider />
      <AnimateToggle />
      <ColorPicker />
      <button
        className="action-button"
        onClick={() => setViewMode(showingPattern ? "3d" : "pattern")}
      >
        {showingPattern ? "View 3D model" : "View crease pattern"}
      </button>
      <FoldImportExport geometry={geometry} />
    </div>
  );
}
