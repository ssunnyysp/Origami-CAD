import { useEffect, useLayoutEffect, useMemo } from "react";
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

// One non-indexed geometry for the whole sheet, allocated once and streamed
// into as the fold advances. Non-indexed so normals stay per-face (flat
// shading), matching folded paper.
export function FlasherMesh({ pattern, positions, color, roughness, metalness }: Props) {
  // Draw order: the vertex id for every triangle corner, fan-triangulated from
  // ids[0] — valid since faces are either triangles or the convex regular-n-gon
  // central polygon, and it must match the triangulation used for the solver's
  // constraints. Depends only on the PATTERN, so it survives foldness changes.
  const order = useMemo(() => {
    const ids: number[] = [];
    for (const face of pattern.faces) {
      const f = face.vertexIds;
      for (let i = 1; i < f.length - 1; i++) {
        ids.push(f[0], f[i], f[i + 1]);
      }
    }
    return new Uint32Array(ids);
  }, [pattern]);

  // Keyed on the pattern, NOT on positions. Keying this on `positions` (which
  // is a fresh Float32Array every frame) meant a new BufferGeometry, a fresh
  // GPU upload and a dispose on every foldness change — the dominant cost in
  // the animation loop, and it scaled with grid size.
  const geometry = useMemo(() => {
    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(order.length * 3), 3));
    geom.setAttribute("normal", new THREE.BufferAttribute(new Float32Array(order.length * 3), 3));
    return geom;
  }, [order]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  // Stream new vertex positions into the existing buffer. computeVertexNormals
  // reuses the normal attribute allocated above rather than allocating one.
  useLayoutEffect(() => {
    const attr = geometry.getAttribute("position") as THREE.BufferAttribute;
    const dst = attr.array as Float32Array;
    for (let i = 0; i < order.length; i++) {
      const src = order[i] * 3;
      const out = i * 3;
      dst[out] = positions[src];
      dst[out + 1] = positions[src + 1];
      dst[out + 2] = positions[src + 2];
    }
    attr.needsUpdate = true;
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();
  }, [geometry, order, positions]);

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
  useEffect(() => () => frontMaterial.dispose(), [frontMaterial]);
  useEffect(() => () => backMaterial.dispose(), [backMaterial]);
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
