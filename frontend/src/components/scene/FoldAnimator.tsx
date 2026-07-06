import { useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useAppStore } from "../../store/useAppStore";

const CYCLE_SECONDS = 9; // one full fold + unfold

// Drives the foldness value through smooth fold/unfold cycles while the
// store's `animating` flag is on. Runs inside the Canvas so it ticks with
// the render loop.
export function FoldAnimator() {
  const animating = useAppStore((s) => s.animating);
  const setFoldness = useAppStore((s) => s.setFoldness);
  const phase = useRef(0);

  // When animation turns on, start the cycle from the current foldness so
  // the model doesn't jump.
  useEffect(() => {
    if (animating) {
      const f = Math.min(1, Math.max(0, useAppStore.getState().foldness));
      phase.current = Math.acos(1 - 2 * f);
    }
  }, [animating]);

  useFrame((_, delta) => {
    if (!animating) return;
    phase.current += (delta * 2 * Math.PI) / CYCLE_SECONDS;
    setFoldness(0.5 - 0.5 * Math.cos(phase.current));
  });

  return null;
}
