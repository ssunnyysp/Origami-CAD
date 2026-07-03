import { useEffect, useMemo } from "react";
import * as THREE from "three";
import type { CreasePattern, CreaseAssignment } from "../../model/types";
import type { VertexPositions } from "../../model/foldEngine";

const CREASE_COLORS: Partial<Record<CreaseAssignment, string>> = {
  mountain: "#d84035",
  valley: "#3560d8",
  border: "#222222",
  // facet edges are triangulation artifacts, not creases — never drawn
};

interface Props {
  pattern: CreasePattern;
  positions: VertexPositions;
}

// CAD-style overlay: mountain (red) / valley (blue) / border (dark) crease
// lines drawn on the folded surface, one LineSegments per assignment.
export function CreaseLines({ pattern, positions }: Props) {
  const geometries = useMemo(() => {
    const coordsByAssignment = new Map<CreaseAssignment, number[]>();
    for (const edge of pattern.edges) {
      if (!(edge.assignment in CREASE_COLORS)) continue;
      const coords = coordsByAssignment.get(edge.assignment) ?? [];
      coords.push(...positions.get(edge.v0)!, ...positions.get(edge.v1)!);
      coordsByAssignment.set(edge.assignment, coords);
    }
    return [...coordsByAssignment].map(([assignment, coords]) => {
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.Float32BufferAttribute(coords, 3));
      return { assignment, geom };
    });
  }, [pattern, positions]);

  useEffect(() => () => geometries.forEach(({ geom }) => geom.dispose()), [geometries]);

  return (
    <>
      {geometries.map(({ assignment, geom }) => (
        <lineSegments key={assignment} geometry={geom}>
          <lineBasicMaterial color={CREASE_COLORS[assignment]} />
        </lineSegments>
      ))}
    </>
  );
}
