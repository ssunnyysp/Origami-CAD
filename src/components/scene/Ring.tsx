import { useMemo } from "react";
import * as THREE from "three";
import type { CreasePattern } from "../../model/types";
import type { RingTransform } from "../../model/foldEngine";
import { ringTransformAtFoldness } from "../../model/foldEngine";
import { FaceMesh } from "./FaceMesh";

interface Props {
  pattern: CreasePattern;
  ringIndex: number;
  target: RingTransform;
  foldness: number;
  color: string;
  roughness: number;
  metalness: number;
}

export function Ring({ pattern, ringIndex, target, foldness, color, roughness, metalness }: Props) {
  const faces = useMemo(
    () => pattern.faces.filter((f) => f.ringIndex === ringIndex),
    [pattern, ringIndex],
  );

  const { position, quaternion } = ringTransformAtFoldness(target, foldness);

  // One material instance per ring, mutated in place so foldness drags
  // (which change every frame) never trigger material re-creation.
  const material = useMemo(
    () => new THREE.MeshStandardMaterial({ side: THREE.DoubleSide }),
    [],
  );
  material.color.set(color);
  material.roughness = roughness;
  material.metalness = metalness;

  return (
    <group position={position} quaternion={quaternion}>
      {faces.map((face) => (
        <FaceMesh key={face.id} pattern={pattern} face={face} material={material} />
      ))}
    </group>
  );
}
