import { useEffect, useState } from "react";
import { useActiveGeometry } from "../../api/useActiveGeometry";
import { useAppStore } from "../../store/useAppStore";
import { Scene } from "../scene/Scene";
import { ControlPanel } from "../ui/ControlPanel";
import { PatternView } from "../pattern/PatternView";
import { CreasePatternAnatomy } from "../anatomy/CreasePatternAnatomy";

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

function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="3" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M7 0.8v1.6M7 11.6v1.6M13.2 7h-1.6M2.4 7H0.8M11.3 2.7l-1.1 1.1M3.8 10.2l-1.1 1.1M11.3 11.3l-1.1-1.1M3.8 3.8 2.7 2.7"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path
        d="M12.4 8.8A5.6 5.6 0 1 1 5.2 1.6a4.5 4.5 0 0 0 7.2 7.2Z"
        stroke="currentColor"
        strokeWidth="1.4"
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
  const theme = useAppStore((s) => s.theme);
  const showGrid = useAppStore((s) => s.showGrid);
  const toggleTheme = useAppStore((s) => s.toggleTheme);
  const paperColor = useAppStore((s) => s.paperColor);
  const roughness = useAppStore((s) => s.roughness);
  const metalness = useAppStore((s) => s.metalness);
  const gridDivisions = useAppStore((s) => s.gridDivisions);
  const layerGapRatio = useAppStore((s) => s.layerGapRatio);
  const heightRatio = useAppStore((s) => s.heightRatio);
  const anatomyOpen = useAppStore((s) => s.anatomyOpen);
  const setAnatomyOpen = useAppStore((s) => s.setAnatomyOpen);
  const [paneOpen, setPaneOpen] = useState(true);

  useEffect(() => {
    loadPresets().catch((err) => console.error("preset load failed:", err));
  }, [loadPresets]);

  // The 3D scene, crease-line colors, and grid all key off this attribute
  // (see index.css) rather than reading the store directly, so plain CSS/
  // Three.js color values can react to theme without a React re-render path.
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const params = { gridDivisions, layerGapRatio, heightRatio };
  // Either the generated preset's geometry or an imported FOLD file's,
  // depending on store.patternSource — see api/useActiveGeometry.ts.
  const { geometry, error: geometryError } = useActiveGeometry(params);

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
            theme={theme}
            showGrid={showGrid}
          />
        )}
        {/* Always mounted once ready (not just while viewMode === "pattern")
            so switching between 3D and crease-pattern view crossfades via
            opacity instead of an abrupt mount/unmount swap. */}
        {ready && (
          <PatternView geometry={geometry} theme={theme} visible={viewMode === "pattern"} />
        )}
        {/* First-load and slow-import feedback — without this the canvas
            just looked empty while a fetch was in flight. */}
        {ready && !geometry && !geometryError && (
          <div className="loading-pill">
            <span className="loading-spinner" />
            Solving fold…
          </div>
        )}
        {/* A failed geometry fetch (backend unreachable, etc.) used to leave
            the "Solving fold…" spinner up forever with no indication
            anything was wrong — surface it instead. */}
        {ready && geometryError && (
          <div className="loading-pill loading-pill--error">
            {geometryError}
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
      {/* Always mounted (not conditionally rendered) so collapsing/reopening
          the panel is a width/opacity transition instead of an instant
          swap — see .task-pane / .is-collapsed in index.css. */}
      <aside
        className={`task-pane${paneOpen ? "" : " is-collapsed"}`}
        aria-hidden={!paneOpen}
        inert={!paneOpen}
      >
        <div className="pane-header">
          <div>
            <h1>Origami CAD</h1>
            <p className="panel-subtitle">Flasher fold simulator</p>
          </div>
          <div className="pane-header-actions">
            <button
              className="theme-toggle"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            >
              <span className="theme-toggle-icon">{theme === "dark" ? <SunIcon /> : <MoonIcon />}</span>
            </button>
            <button
              className="pane-toggle"
              onClick={() => setPaneOpen(false)}
              aria-label="Collapse panel"
              title="Collapse panel"
              tabIndex={paneOpen ? 0 : -1}
            >
              <ChevronRightIcon />
            </button>
          </div>
        </div>
        <ControlPanel geometry={geometry} />
      </aside>
      {anatomyOpen && <CreasePatternAnatomy onClose={() => setAnatomyOpen(false)} />}
    </div>
  );
}
