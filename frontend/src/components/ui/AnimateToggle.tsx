import { useAppStore } from "../../store/useAppStore";

export function AnimateToggle() {
  const animating = useAppStore((s) => s.animating);
  const setAnimating = useAppStore((s) => s.setAnimating);

  return (
    <label className="control-row">
      <span>Animate</span>
      <span className="switch">
        <input type="checkbox" checked={animating} onChange={(e) => setAnimating(e.target.checked)} />
        <span className="switch-track" aria-hidden="true">
          <span className="switch-thumb" />
        </span>
      </span>
      <span className="control-value">{animating ? "folding" : "off"}</span>
    </label>
  );
}
