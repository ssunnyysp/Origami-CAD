import type { FlasherGeometry } from "./types";

// Positions at an arbitrary foldness, interpolated between the server-solved
// frames. Samples are uniformly spaced, so the frame index comes straight from
// the foldness value — no search needed.
//
// CATMULL-ROM, not linear. Linear interpolation makes each frame interval a
// straight line, so velocity changes abruptly at every frame boundary and the
// fold reads as a series of small jerks — very visible at this fold depth,
// where the sheet can move most of a grid cell between frames. Catmull-Rom is
// C1-continuous through the sample points, so velocity carries across
// boundaries and the motion looks continuous. It costs one extra pair of taps
// per component and no extra memory or network payload.
//
// Endpoints are preserved exactly: the tangent neighbours are clamped, so
// foldness 0 returns frame 0 (the perfectly flat sheet) and foldness 1 returns
// the final solved frame, both untouched.
export function interpolatePositions(geometry: FlasherGeometry, foldness: number): Float32Array {
  const { frames } = geometry;
  const last = frames.length - 1;
  const t = Math.min(1, Math.max(0, foldness));

  const x = t * last;
  const i1 = Math.min(last, Math.floor(x));
  const frac = x - i1;

  const f1 = frames[i1];
  const out = new Float32Array(f1.length);

  // Exactly on a sample (includes both endpoints) — copy it through untouched.
  if (frac === 0) {
    out.set(f1);
    return out;
  }

  const i2 = Math.min(last, i1 + 1);
  const i0 = Math.max(0, i1 - 1);
  const i3 = Math.min(last, i1 + 2);
  const f0 = frames[i0];
  const f2 = frames[i2];
  const f3 = frames[i3];

  // Uniform Catmull-Rom basis at `frac`.
  const t2 = frac * frac;
  const t3 = t2 * frac;
  const b0 = -0.5 * t3 + t2 - 0.5 * frac;
  const b1 = 1.5 * t3 - 2.5 * t2 + 1;
  const b2 = -1.5 * t3 + 2 * t2 + 0.5 * frac;
  const b3 = 0.5 * t3 - 0.5 * t2;

  for (let k = 0; k < f1.length; k++) {
    out[k] = f0[k] * b0 + f1[k] * b1 + f2[k] * b2 + f3[k] * b3;
  }
  return out;
}
