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
  const gridDivisions = useAppStore((s) => s.gridDivisions);
  const wrapPerRing = useAppStore((s) => s.wrapPerRing);
  const layerGapRatio = useAppStore((s) => s.layerGapRatio);
  const heightRatio = useAppStore((s) => s.heightRatio);

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
            params={{ gridDivisions, wrapPerRing, layerGapRatio, heightRatio }}
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
