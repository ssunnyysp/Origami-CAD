import * as THREE from "three";
import type { FlasherParams } from "./flasherGenerator";

// Each concentric ring is animated as a single rigid body rather than solving
// per-triangle hinge angles: a full numeric rigid-origami solver is
// over-determined for arbitrary user-chosen (sides, ratio, twist) — verified
// separately that closed-form per-hinge angles don't generally exist for free
// parameter choices. Treating each ring as one rigid group guarantees an
// exact, non-self-intersecting result at both foldness=0 (flat) and
// foldness=1 (fully folded stack), since rings only differ by an in-plane
// rotation and a z-height offset. Mid-fold, individual triangles are not
// physically rigid (radial spokes stretch slightly) — acceptable for a
// showcase fold slider.
const RING_SPACING_RATIO = 0.15; // fraction of centralRadius of height gained per ring at full fold

export interface RingTransform {
  ringIndex: number;
  position: THREE.Vector3; // target translation at foldness = 1
  quaternion: THREE.Quaternion; // target rotation at foldness = 1
}

export function computeRingTransforms(params: FlasherParams): RingTransform[] {
  const ringSpacing = params.centralRadius * RING_SPACING_RATIO;
  const axis = new THREE.Vector3(0, 0, 1);
  const transforms: RingTransform[] = [];
  for (let j = 0; j <= params.rings; j++) {
    transforms.push({
      ringIndex: j,
      position: new THREE.Vector3(0, 0, j * ringSpacing),
      quaternion: new THREE.Quaternion().setFromAxisAngle(axis, j * params.twistAngle),
    });
  }
  return transforms;
}

const IDENTITY_QUATERNION = new THREE.Quaternion();
const ORIGIN = new THREE.Vector3(0, 0, 0);

// Interpolates a ring's rigid transform between flat (t=0, identity) and
// fully folded (t=1, the ring's target transform).
export function ringTransformAtFoldness(
  target: RingTransform,
  t: number,
): { position: THREE.Vector3; quaternion: THREE.Quaternion } {
  return {
    position: new THREE.Vector3().lerpVectors(ORIGIN, target.position, t),
    quaternion: new THREE.Quaternion().slerpQuaternions(IDENTITY_QUATERNION, target.quaternion, t),
  };
}
