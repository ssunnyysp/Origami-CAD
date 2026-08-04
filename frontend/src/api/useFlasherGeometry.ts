import { useEffect, useState } from "react";
import type { FlasherGeometry, FlasherParams } from "../model/types";
import { fetchGeometry } from "./client";

export interface FlasherGeometryResult {
  geometry: FlasherGeometry | null;
  error: string | null;
}

// Fetches solved geometry whenever the flasher parameters change. The
// previous geometry is kept on screen while the new one loads so parameter
// changes never blank the canvas. A failed fetch (backend down, bad params)
// is surfaced as `error` instead of only logging to the console — otherwise
// the UI was left showing an infinite "Solving fold…" spinner with no way
// for the user to tell something went wrong.
export function useFlasherGeometry(params: FlasherParams): FlasherGeometryResult {
  const [geometry, setGeometry] = useState<FlasherGeometry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { gridDivisions, layerGapRatio, heightRatio } = params;

  useEffect(() => {
    let stale = false;
    setError(null);
    fetchGeometry({ gridDivisions, layerGapRatio, heightRatio })
      .then((g) => {
        if (!stale) setGeometry(g);
      })
      .catch((err) => {
        if (stale) return;
        const message = err instanceof Error ? err.message : String(err);
        console.error("geometry fetch failed:", err);
        setError(message);
      });
    return () => {
      stale = true;
    };
  }, [gridDivisions, layerGapRatio, heightRatio]);

  return { geometry, error };
}
