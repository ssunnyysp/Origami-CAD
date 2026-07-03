import type { FlasherParams } from "./flasherGenerator";
import { flasherVertexId } from "./flasherGenerator";

// Fold model: per-vertex interpolation in CYLINDRICAL coordinates between the
// flat pattern (z = 0) and a wrapped target state in which each successive
// ring winds `wrapAngle` further around the hub, sits at a slightly larger
// layer radius (imitating accumulated layer thickness), and rises in z.
//
// Interpolating (radius, angle, height) independently — with the angle left
// unwrapped, so outer rings sweep through multiple turns — makes the sheet
// visibly coil around the hub as foldness increases, which is the signature
// stow/deploy motion of a flasher.
//
// This is a showcase kinematic, not a rigid-origami solution: triangle edge
// lengths are not preserved mid-fold (or exactly at foldness = 1). A true
// flasher additionally needs pleated arms to wrap isometrically — see
// docs/FLASHER_NOTES.md for the exact math and the roadmap toward it.
const LAYER_GAP_RATIO = 0.08; // fraction of centralRadius of layer-radius growth per wrapped ring
const HEIGHT_RATIO = 0.8; // fraction of the flat radial band width converted to stowed height

export type VertexPositions = Map<number, [number, number, number]>;

export function computeVertexPositionsAtFoldness(
  params: FlasherParams,
  foldness: number,
): VertexPositions {
  const { sides: n, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius } = params;
  const t = Math.min(1, Math.max(0, foldness));
  const layerGap = centralRadius * LAYER_GAP_RATIO;

  const positions: VertexPositions = new Map();
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

      positions.set(flasherVertexId(n, j, i), [
        radius * Math.cos(angle),
        radius * Math.sin(angle),
        z,
      ]);
    }
  }
  return positions;
}
