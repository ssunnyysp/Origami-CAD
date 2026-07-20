import type { FlasherGeometry, FlasherParams } from "../model/types";
import { useAppStore } from "../store/useAppStore";
import { useFlasherGeometry } from "./useFlasherGeometry";

export interface ActiveGeometryResult {
  geometry: FlasherGeometry | null;
  error: string | null;
}

// Whatever the scene should currently render: the generated preset's
// geometry, or an imported FOLD file's geometry, depending on
// store.patternSource. useFlasherGeometry is always called (hooks can't be
// conditional) — its fetch is simply unused while an import is showing,
// which costs an unused network request but keeps the preset geometry warm
// for switching back. `error` only ever reflects the generated fetch —
// import failures already have their own surfaced `importError` in the store.
export function useActiveGeometry(params: FlasherParams): ActiveGeometryResult {
  const source = useAppStore((s) => s.patternSource);
  const imported = useAppStore((s) => s.importedGeometry);
  const { geometry: generated, error } = useFlasherGeometry(params);
  return source === "imported" ? { geometry: imported, error: null } : { geometry: generated, error };
}
