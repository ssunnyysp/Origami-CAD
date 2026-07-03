import { useEffect, useMemo } from "react";
import * as THREE from "three";
import type { CreasePattern } from "../../model/types";
import type { VertexPositions } from "../../model/foldEngine";

interface Props {
  pattern: CreasePattern;
  positions: VertexPositions;
  color: string;
  roughness: number;
  metalness: number;
}

// One non-indexed geometry for the whole sheet, rebuilt from the fold
// engine's interpolated vertex positions. Non-indexed so normals stay
// per-face (flat shading), matching folded paper.
export function FlasherMesh({ pattern, positions, color, roughness, metalness }: Props) {
  const geometry = useMemo(() => {
    const coords: number[] = [];
    for (const face of pattern.faces) {
      const points = face.vertexIds.map((id) => positions.get(id)!);
      // Fan triangulation from points[0] — valid since faces are either
      // triangles or the convex regular-n-gon central polygon.
      for (let i = 1; i < points.length - 1; i++) {
        coords.push(...points[0], ...points[i], ...points[i + 1]);
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
