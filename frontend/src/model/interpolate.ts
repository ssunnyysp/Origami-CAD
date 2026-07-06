import type { FlasherGeometry } from "./types";

// Positions at an arbitrary foldness, by linear interpolation between the two
// nearest server-solved frames. Samples are uniformly spaced, so the frame
// index comes straight from the foldness value — no search needed.
export function interpolatePositions(geometry: FlasherGeometry, foldness: number): Float32Array {
  const { frames } = geometry;
  const t = Math.min(1, Math.max(0, foldness));

  const x = t * (frames.length - 1);
  const i0 = Math.min(frames.length - 1, Math.floor(x));
  const i1 = Math.min(frames.length - 1, i0 + 1);
  const frac = x - i0;

  const f0 = frames[i0];
  const f1 = frames[i1];
  const out = new Float32Array(f0.length);
  for (let k = 0; k < f0.length; k++) {
    out[k] = f0[k] + (f1[k] - f0[k]) * frac;
  }
  return out;
}
