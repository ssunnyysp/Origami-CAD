import { useEffect, useMemo } from "react";
import * as THREE from "three";
import type { CreasePattern, CreaseAssignment } from "../../model/types";

// Mountain folds up (blue), valley folds down (red).
const CREASE_COLORS: Partial<Record<CreaseAssignment, string>> = {
  mountain: "#3560d8",
  valley: "#d84035",
  border: "#222222",
  // facet edges are triangulation artifacts, not creases — never drawn
};

interface Props {
  pattern: CreasePattern;
  positions: Float32Array; // xyz triples indexed by vertex id
  foldness: number;
}

// CAD-style overlay: mountain (red) / valley (blue) / border (dark) crease
// lines, fading out as the model folds so the stowed form reads as plain
// paper rather than a wireframe.
export function CreaseLines({ pattern, positions, foldness }: Props) {
  const opacity = Math.max(0, 1 - foldness * 1.5);

  const geometries = useMemo(() => {
    const coordsByAssignment = new Map<CreaseAssignment, number[]>();
    for (const edge of pattern.edges) {
      if (!(edge.assignment in CREASE_COLORS)) continue;
      const coords = coordsByAssignment.get(edge.assignment) ?? [];
      for (const id of [edge.v0, edge.v1]) {
        coords.push(positions[id * 3], positions[id * 3 + 1], positions[id * 3 + 2]);
      }
      coordsByAssignment.set(edge.assignment, coords);
    }
    return [...coordsByAssignment].map(([assignment, coords]) => {
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.Float32BufferAttribute(coords, 3));
      return { assignment, geom };
    });
  }, [pattern, positions]);

  useEffect(() => () => geometries.forEach(({ geom }) => geom.dispose()), [geometries]);

  if (opacity <= 0) return null;

  return (
    <>
      {geometries.map(({ assignment, geom }) => (
        <lineSegments key={assignment} geometry={geom}>
          <lineBasicMaterial color={CREASE_COLORS[assignment]} transparent opacity={opacity} />
        </lineSegments>
      ))}
    </>
  );
}
