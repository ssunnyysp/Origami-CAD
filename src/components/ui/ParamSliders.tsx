import { useAppStore } from "../../store/useAppStore";

export function ParamSliders() {
  const sides = useAppStore((s) => s.sides);
  const setSides = useAppStore((s) => s.setSides);
  const rings = useAppStore((s) => s.rings);
  const setRings = useAppStore((s) => s.setRings);
  const spiralAngleDeg = useAppStore((s) => s.spiralAngleDeg);
  const setSpiralAngleDeg = useAppStore((s) => s.setSpiralAngleDeg);
  const wrapAngleDeg = useAppStore((s) => s.wrapAngleDeg);
  const setWrapAngleDeg = useAppStore((s) => s.setWrapAngleDeg);
  const radiusRatio = useAppStore((s) => s.radiusRatio);
  const setRadiusRatio = useAppStore((s) => s.setRadiusRatio);
  const roughness = useAppStore((s) => s.roughness);
  const setRoughness = useAppStore((s) => s.setRoughness);
  const metalness = useAppStore((s) => s.metalness);
  const setMetalness = useAppStore((s) => s.setMetalness);
  const showCreases = useAppStore((s) => s.showCreases);
  const setShowCreases = useAppStore((s) => s.setShowCreases);

  return (
    <>
      <label className="control-row">
        <span>Sides</span>
        <input
          type="range"
          min={3}
          max={10}
          step={1}
          value={sides}
          onChange={(e) => setSides(Number(e.target.value))}
        />
        <span className="control-value">{sides}</span>
      </label>

      <label className="control-row">
        <span>Rings</span>
        <input
          type="range"
          min={1}
          max={10}
          step={1}
          value={rings}
          onChange={(e) => setRings(Number(e.target.value))}
        />
        <span className="control-value">{rings}</span>
      </label>

      <label className="control-row">
        <span>Spiral angle</span>
        <input
          type="range"
          min={0}
          max={45}
          step={1}
          value={spiralAngleDeg}
          onChange={(e) => setSpiralAngleDeg(Number(e.target.value))}
        />
        <span className="control-value">{spiralAngleDeg}°</span>
      </label>

      <label className="control-row">
        <span>Wrap per ring</span>
        <input
          type="range"
          min={0}
          max={180}
          step={1}
          value={wrapAngleDeg}
          onChange={(e) => setWrapAngleDeg(Number(e.target.value))}
        />
        <span className="control-value">{wrapAngleDeg}°</span>
      </label>

      <label className="control-row">
        <span>Ring spread</span>
        <input
          type="range"
          min={1.1}
          max={2}
          step={0.01}
          value={radiusRatio}
          onChange={(e) => setRadiusRatio(Number(e.target.value))}
        />
        <span className="control-value">{radiusRatio.toFixed(2)}</span>
      </label>

      <label className="control-row">
        <span>Roughness</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={roughness}
          onChange={(e) => setRoughness(Number(e.target.value))}
        />
        <span className="control-value">{roughness.toFixed(2)}</span>
      </label>

      <label className="control-row">
        <span>Metalness</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={metalness}
          onChange={(e) => setMetalness(Number(e.target.value))}
        />
        <span className="control-value">{metalness.toFixed(2)}</span>
      </label>

      <label className="control-row">
        <span>Show creases</span>
        <input
          type="checkbox"
          checked={showCreases}
          onChange={(e) => setShowCreases(e.target.checked)}
        />
        <span className="control-value">{showCreases ? "on" : "off"}</span>
      </label>
    </>
  );
}
