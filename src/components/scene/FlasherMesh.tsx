import { useEffect, useMemo } from "react";
import * as THREE from "three";
import type { CreasePattern } from "../../model/types";

interface Props {
  pattern: CreasePattern;
  positions: Float32Array; // xyz triples indexed by vertex id
  color: string;
  roughness: number;
  metalness: number;
}

// One non-indexed geometry for the whole sheet, rebuilt from the solver's
// vertex positions. Non-indexed so normals stay per-face (flat shading),
// matching folded paper.
export function FlasherMesh({ pattern, positions, color, roughness, metalness }: Props) {
  const geometry = useMemo(() => {
    const coords: number[] = [];
    for (const face of pattern.faces) {
      const ids = face.vertexIds;
      // Fan triangulation from ids[0] — valid since faces are either
      // triangles or the convex regular-n-gon central polygon. Must match
      // the triangulation used for the solver's constraints.
      for (let i = 1; i < ids.length - 1; i++) {
        for (const id of [ids[0], ids[i], ids[i + 1]]) {
          coords.push(positions[id * 3], positions[id * 3 + 1], positions[id * 3 + 2]);
        }
      }
    }
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.Float32BufferAttribute(coords, 3));
    geom.computeVertexNormals();
    return geom;
  }, [pattern, positions]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  // One material instance, mutated in place so color/foldness drags never
  // trigger material re-creation. polygonOffset pushes the surface back so
  // the crease-line overlay doesn't z-fight.
  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        side: THREE.DoubleSide,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
      }),
    [],
  );
  material.color.set(color);
  material.roughness = roughness;
  material.metalness = metalness;

  return <mesh geometry={geometry} material={material} />;
}
