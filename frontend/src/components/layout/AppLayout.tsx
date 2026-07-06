import { useEffect } from "react";
import { useAppStore } from "../../store/useAppStore";
import { Scene } from "../scene/Scene";
import { ControlPanel } from "../ui/ControlPanel";

export function AppLayout() {
  const ready = useAppStore((s) => s.ready);
  const loadPresets = useAppStore((s) => s.loadPresets);
  const foldness = useAppStore((s) => s.foldness);
  const paperColor = useAppStore((s) => s.paperColor);
  const roughness = useAppStore((s) => s.roughness);
  const metalness = useAppStore((s) => s.metalness);
  const sides = useAppStore((s) => s.sides);
  const rings = useAppStore((s) => s.rings);
  const spiralAngleDeg = useAppStore((s) => s.spiralAngleDeg);
  const wrapAngleDeg = useAppStore((s) => s.wrapAngleDeg);
  const radiusRatio = useAppStore((s) => s.radiusRatio);
  const centralRadius = useAppStore((s) => s.centralRadius);

  useEffect(() => {
    loadPresets().catch((err) => console.error("preset load failed:", err));
  }, [loadPresets]);

  return (
    <div className="app-layout">
      <div className="canvas-area">
        {/* Scene mounts only once presets are applied — its camera distance is
            fixed at mount, so it must see real parameters, not placeholders. */}
        {ready && (
          <Scene
            params={{ sides, rings, spiralAngleDeg, wrapAngleDeg, radiusRatio, centralRadius }}
            foldness={foldness}
            color={paperColor}
            roughness={roughness}
            metalness={metalness}
            autoRotate
          />
        )}
      </div>
      <ControlPanel />
    </div>
  );
}
