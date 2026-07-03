import type { FlasherParams } from "./flasherGenerator";

// Kinematic wrap target: each vertex's goal position in CYLINDRICAL
// coordinates between the flat pattern (z = 0) and a wrapped state in which
// each successive ring winds `wrapAngle` further around the hub, sits at a
// slightly larger layer radius (imitating accumulated layer thickness), and
// rises in z. This target is NOT length-preserving — it is only the
// attractor that FlasherFoldSolver pulls toward while enforcing that every
// edge keeps its flat (paper) length.
const LAYER_GAP_RATIO = 0.06; // fraction of centralRadius of layer-radius growth per wrapped ring
const HEIGHT_RATIO = 0.8; // fraction of the flat radial band width converted to stowed height

// Writes xyz triples indexed by vertex id (id = ring * sides + sector).
export function computeTargetPositions(params: FlasherParams, foldness: number): Float64Array {
  const { sides: n, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius } = params;
  const t = Math.min(1, Math.max(0, foldness));
  const layerGap = centralRadius * LAYER_GAP_RATIO;

  const out = new Float64Array((rings + 1) * n * 3);
  for (let j = 0; j <= rings; j++) {
    const flatRadius = centralRadius * Math.pow(radiusRatio, j);
    const foldedRadius = centralRadius + j * layerGap;
    // Stowed height grows with the flat material consumed so far, so wider
    // rings produce a taller stowed cylinder (material conservation-ish).
    const foldedZ = HEIGHT_RATIO * (flatRadius - centralRadius);

    const radius = flatRadius + (foldedRadius - flatRadius) * t;
    const z = foldedZ * t;

    for (let i = 0; i < n; i++) {
      const baseAngle = (2 * Math.PI * i) / n;
      const flatAngle = baseAngle + j * spiralAngle;
      const foldedAngle = baseAngle + j * wrapAngle;
      const angle = flatAngle + (foldedAngle - flatAngle) * t;

      const k = (j * n + i) * 3;
      out[k] = radius * Math.cos(angle);
      out[k + 1] = radius * Math.sin(angle);
      out[k + 2] = z;
    }
  }
  return out;
}
