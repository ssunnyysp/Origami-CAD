import { useAppStore } from "../../store/useAppStore";

// Shows/hides all of the scene's reference geometry — the three coordinate-plane
// grids and the origin axis rays — as one switch. They are a single visual
// layer ("where is this thing in space"), so splitting them across two controls
// would leave the axes floating with no plane to read them against.
export function GridToggle() {
  const showGrid = useAppStore((s) => s.showGrid);
  const setShowGrid = useAppStore((s) => s.setShowGrid);

  return (
    <label className="control-row">
      <span>Grid</span>
      <span className="switch">
        <input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} />
        <span className="switch-track" aria-hidden="true">
          <span className="switch-thumb" />
        </span>
      </span>
      <span className="control-value">{showGrid ? "on" : "off"}</span>
    </label>
  );
}
