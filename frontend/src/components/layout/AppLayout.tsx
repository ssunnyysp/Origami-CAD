import { useEffect, useState } from "react";
import { useActiveGeometry } from "../../api/useActiveGeometry";
import { useAppStore } from "../../store/useAppStore";
import { Scene } from "../scene/Scene";
import { ControlPanel } from "../ui/ControlPanel";
import { PatternView } from "../pattern/PatternView";

function ChevronLeftIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
      <path
        d="M9.5 3.5 5 7.5l4.5 4"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
      <path
        d="M5.5 3.5 10 7.5l-4.5 4"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

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
  // Either the generated preset's geometry or an imported FOLD file's,
  // depending on store.patternSource — see api/useActiveGeometry.ts.
  const geometry = useActiveGeometry(params);

  return (
    <div className="app-layout">
      <div className="canvas-area">
        {/* Scene mounts only once presets are applied — it must see real
            parameters, not placeholders. It stays mounted under the pattern
            view so switching back never rebuilds the WebGL context. */}
        {ready && (
          <Scene
            geometry={geometry}
            foldness={foldness}
            color={paperColor}
            roughness={roughness}
            metalness={metalness}
          />
        )}
        {ready && viewMode === "pattern" && <PatternView geometry={geometry} />}
        {/* First-load and slow-import feedback — without this the canvas
            just looked empty while a fetch was in flight. */}
        {ready && !geometry && (
          <div className="loading-pill">
            <span className="loading-spinner" />
            Solving fold…
          </div>
        )}
        {!paneOpen && (
          <button
            className="pane-reopen"
            onClick={() => setPaneOpen(true)}
            aria-label="Open panel"
            title="Open panel"
          >
            <ChevronLeftIcon />
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
              <ChevronRightIcon />
            </button>
          </div>
          <ControlPanel geometry={geometry} />
        </aside>
      )}
    </div>
  );
}
