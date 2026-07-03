import { useAppStore } from "../../store/useAppStore";
import { Scene } from "../scene/Scene";
import { ControlPanel } from "../ui/ControlPanel";

export function AppLayout() {
  const foldness = useAppStore((s) => s.foldness);
  const paperColor = useAppStore((s) => s.paperColor);
  const roughness = useAppStore((s) => s.roughness);
  const metalness = useAppStore((s) => s.metalness);
  const sides = useAppStore((s) => s.sides);
  const rings = useAppStore((s) => s.rings);
  const twistAngleDeg = useAppStore((s) => s.twistAngleDeg);
  const radiusRatio = useAppStore((s) => s.radiusRatio);
  const centralRadius = useAppStore((s) => s.centralRadius);

  return (
    <div className="app-layout">
      <div className="canvas-area">
        <Scene
          params={{
            sides,
            rings,
            twistAngle: (twistAngleDeg * Math.PI) / 180,
            radiusRatio,
            centralRadius,
          }}
          foldness={foldness}
          color={paperColor}
          roughness={roughness}
          metalness={metalness}
          autoRotate
        />
      </div>
      <ControlPanel />
    </div>
  );
}
