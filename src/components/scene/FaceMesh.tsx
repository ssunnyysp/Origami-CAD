import { useMemo } from "react";
import * as THREE from "three";
import type { CreasePattern, Face } from "../../model/types";

interface Props {
  pattern: CreasePattern;
  face: Face;
  material: THREE.Material;
}

// Static geometry built once from the flat-pattern 2D coordinates, embedded
// in the XY plane. Folding is applied entirely via the parent Ring group's
// transform, never by mutating these vertices.
export function FaceMesh({ pattern, face, material }: Props) {
  const geometry = useMemo(() => {
    const vertexById = new Map(pattern.vertices.map((v) => [v.id, v]));
    const points = face.vertexIds.map((id) => vertexById.get(id)!.position);

    const positions: number[] = [];
    // Fan triangulation from points[0] — valid since faces are either
    // triangles or the convex regular-n-gon central polygon.
    for (let i = 1; i < points.length - 1; i++) {
      positions.push(points[0].x, points[0].y, 0);
      positions.push(points[i].x, points[i].y, 0);
      positions.push(points[i + 1].x, points[i + 1].y, 0);
    }

    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geom.computeVertexNormals();
    return geom;
  }, [pattern, face]);

  return <mesh geometry={geometry} material={material} />;
}
