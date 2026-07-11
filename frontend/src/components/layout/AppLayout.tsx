import { useEffect, useState } from "react";
import { useAppStore } from "../../store/useAppStore";
import { Scene } from "../scene/Scene";
import { ControlPanel } from "../ui/ControlPanel";
import { PatternView } from "../pattern/PatternView";

export function AppLayout() {
  const ready = useAppStore((s) => s.ready);
  const loadPresets = useAppStore((s) => s.loadPresets);
  const viewMode = useAppStore((s) => s.viewMode);
  const foldness = useAppStore((s) => s.foldness);
  const paperColor = useAppStore((s) => s.paperColor);
  const roughness = useAppStore((s) => s.roughness);
  const metalness = useAppStore((s) => s.metalness);
  const gridDivisions = useAppStore((s) => s.gridDivisions);
  const layerGapRatio = useAppStore((s) => s.layerGapRatio);
  const heightRatio = useAppStore((s) => s.heightRatio);
  const [paneOpen, setPaneOpen] = useState(true);

  useEffect(() => {
    loadPresets().catch((err) => console.error("preset load failed:", err));
  }, [loadPresets]);

  const params = { gridDivisions, layerGapRatio, heightRatio };

  return (
    <div className="app-layout">
      <div className="canvas-area">
        {/* Scene mounts only once presets are applied — it must see real
            parameters, not placeholders. It stays mounted under the pattern
            view so switching back never rebuilds the WebGL context. */}
        {ready && (
          <Scene
            params={params}
            foldness={foldness}
            color={paperColor}
            roughness={roughness}
            metalness={metalness}
          />
        )}
        {ready && viewMode === "pattern" && <PatternView params={params} />}
        {!paneOpen && (
          <button
            className="pane-reopen"
            onClick={() => setPaneOpen(true)}
            aria-label="Open panel"
            title="Open panel"
          >
            ⟨
          </button>
        )}
      </div>
      {paneOpen && (
        <aside className="task-pane">
          <div className="pane-header">
            <div>
              <h1>Origami CAD</h1>
              <p className="panel-subtitle">Flasher fold simulator</p>
            </div>
            <button
              className="pane-toggle"
              onClick={() => setPaneOpen(false)}
              aria-label="Collapse panel"
              title="Collapse panel"
            >
              ⟩
            </button>
          </div>
          <ControlPanel />
        </aside>
      )}
    </div>
  );
}
