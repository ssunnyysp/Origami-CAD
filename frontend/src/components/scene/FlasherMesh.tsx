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

// The back of the sheet is always plain paper — origami paper is colored on
// one side only, and the two-tone folds are part of the look.
const PLAIN_PAPER = "#eef0f3";

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

  // Two materials over the same geometry: faces wind CCW in the flat pattern,
  // so FrontSide is the sheet's top (the colored side) and BackSide is the
  // underside (plain paper). Material instances are mutated in place so
  // color/foldness drags never trigger material re-creation; polygonOffset
  // pushes the surface back so the crease-line overlay doesn't z-fight.
  const frontMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        side: THREE.FrontSide,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
      }),
    [],
  );
  const backMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        side: THREE.BackSide,
        color: PLAIN_PAPER,
        roughness: 0.92,
        metalness: 0,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
      }),
    [],
  );
  frontMaterial.color.set(color);
  frontMaterial.roughness = roughness;
  frontMaterial.metalness = metalness;

  return (
    <>
      <mesh geometry={geometry} material={frontMaterial} />
      <mesh geometry={geometry} material={backMaterial} />
    </>
  );
}
