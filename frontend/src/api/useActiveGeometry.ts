import type { FlasherGeometry, FlasherParams } from "../model/types";
import { useAppStore } from "../store/useAppStore";
import { useFlasherGeometry } from "./useFlasherGeometry";

// Whatever the scene should currently render: the generated preset's
// geometry, or an imported FOLD file's geometry, depending on
// store.patternSource. useFlasherGeometry is always called (hooks can't be
// conditional) — its fetch is simply unused while an import is showing,
// which costs an unused network request but keeps the preset geometry warm
// for switching back.
export function useActiveGeometry(params: FlasherParams): FlasherGeometry | null {
  const source = useAppStore((s) => s.patternSource);
  const imported = useAppStore((s) => s.importedGeometry);
  const generated = useFlasherGeometry(params);
  return source === "imported" ? imported : generated;
}
