import { useAppStore } from "../../store/useAppStore";

export function FoldnessSlider() {
  const foldness = useAppStore((s) => s.foldness);
  const setFoldness = useAppStore((s) => s.setFoldness);
  const setAnimating = useAppStore((s) => s.setAnimating);

  return (
    <label className="control-row">
      <span>Foldness</span>
      <input
        type="range"
        min={0}
        max={1}
        step={0.001}
        value={foldness}
        onChange={(e) => {
          // Manual dragging takes over from the animation loop.
          setAnimating(false);
          setFoldness(Number(e.target.value));
        }}
      />
      <span className="control-value">{Math.round(foldness * 100)}%</span>
    </label>
  );
}
