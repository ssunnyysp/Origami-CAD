import { useAppStore } from "../../store/useAppStore";

export function ParamSliders() {
  const rings = useAppStore((s) => s.rings);
  const setRings = useAppStore((s) => s.setRings);
  const twistAngleDeg = useAppStore((s) => s.twistAngleDeg);
  const setTwistAngleDeg = useAppStore((s) => s.setTwistAngleDeg);
  const radiusRatio = useAppStore((s) => s.radiusRatio);
  const setRadiusRatio = useAppStore((s) => s.setRadiusRatio);
  const roughness = useAppStore((s) => s.roughness);
  const setRoughness = useAppStore((s) => s.setRoughness);
  const metalness = useAppStore((s) => s.metalness);
  const setMetalness = useAppStore((s) => s.setMetalness);

  return (
    <>
      <label className="control-row">
        <span>Rings</span>
        <input
          type="range"
          min={1}
          max={6}
          step={1}
          value={rings}
          onChange={(e) => setRings(Number(e.target.value))}
        />
        <span className="control-value">{rings}</span>
      </label>

      <label className="control-row">
        <span>Twist angle</span>
        <input
          type="range"
          min={0}
          max={90}
          step={1}
          value={twistAngleDeg}
          onChange={(e) => setTwistAngleDeg(Number(e.target.value))}
        />
        <span className="control-value">{twistAngleDeg}°</span>
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
    </>
  );
}
