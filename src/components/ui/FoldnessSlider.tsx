import { useAppStore } from "../../store/useAppStore";

export function FoldnessSlider() {
  const foldness = useAppStore((s) => s.foldness);
  const setFoldness = useAppStore((s) => s.setFoldness);

  return (
    <label className="control-row">
      <span>Foldness</span>
      <input
        type="range"
        min={0}
        max={1}
        step={0.001}
        value={foldness}
        onChange={(e) => setFoldness(Number(e.target.value))}
      />
      <span className="control-value">{Math.round(foldness * 100)}%</span>
    </label>
  );
}
