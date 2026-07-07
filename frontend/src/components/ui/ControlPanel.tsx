import { useAppStore } from "../../store/useAppStore";
import { ModelSelector } from "./ModelSelector";
import { FoldnessSlider } from "./FoldnessSlider";
import { AnimateToggle } from "./AnimateToggle";
import { ColorPicker } from "./ColorPicker";

export function ControlPanel() {
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
    </div>
  );
}
