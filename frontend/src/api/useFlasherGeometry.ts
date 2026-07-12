import { useEffect, useState } from "react";
import type { FlasherGeometry, FlasherParams } from "../model/types";
import { fetchGeometry } from "./client";

// Fetches solved geometry whenever the flasher parameters change. The
// previous geometry is kept on screen while the new one loads so parameter
// changes never blank the canvas.
export function useFlasherGeometry(params: FlasherParams): FlasherGeometry | null {
  const [geometry, setGeometry] = useState<FlasherGeometry | null>(null);
  const { sides, rings, pleatRatio, twistRatio } = params;

  useEffect(() => {
    let stale = false;
    fetchGeometry({ sides, rings, pleatRatio, twistRatio })
      .then((g) => {
        if (!stale) setGeometry(g);
      })
      .catch((err) => {
        if (!stale) console.error("geometry fetch failed:", err);
      });
    return () => {
      stale = true;
    };
  }, [sides, rings, pleatRatio, twistRatio]);

  return geometry;
}
