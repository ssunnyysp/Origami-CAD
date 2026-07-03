import type { CreasePattern, Vertex, Edge, Face, FaceAdjacency, CreaseAssignment } from "./types";

export interface FlasherParams {
  sides: number; // n, number of sides of the central polygon / rings
  rings: number; // k, number of concentric pleat rings around the central polygon
  twistAngle: number; // radians; folded-state rotation increment per ring (used by the fold engine, not the flat layout)
  radiusRatio: number; // > 1, each ring's outer radius = inner radius * radiusRatio
  centralRadius: number; // r0, circumradius of the central polygon in flat-pattern units
}

// Ring-boundary creases alternate mountain/valley by ring parity; radial spokes
// take the opposite parity; sector diagonals are always valley. This is a
// simplified, self-consistent labeling rule for visualizing the crease
// pattern — it is not derived from a global flat-foldability proof, and the
// fold engine does not depend on these directions (it animates whole rings
// as rigid bodies). A future per-hinge solver would need to re-derive these
// properly.
function ringBoundaryAssignment(ringIndex: number): "mountain" | "valley" {
  return ringIndex % 2 === 0 ? "mountain" : "valley";
}

function radialSpokeAssignment(ringIndex: number): "mountain" | "valley" {
  return ringBoundaryAssignment(ringIndex) === "mountain" ? "valley" : "mountain";
}

export function generateFlasher(params: FlasherParams): CreasePattern {
  const { sides: n, rings, radiusRatio, centralRadius } = params;

  const vertices: Vertex[] = [];
  const vertexId = (ring: number, i: number) => ring * n + ((i % n) + n) % n;

  // Ring radii: R[0] = centralRadius, R[j] = R[j-1] * radiusRatio
  const radii: number[] = [centralRadius];
  for (let j = 1; j <= rings; j++) radii.push(radii[j - 1] * radiusRatio);

  for (let j = 0; j <= rings; j++) {
    for (let i = 0; i < n; i++) {
      const angle = (2 * Math.PI * i) / n;
      vertices.push({
        id: vertexId(j, i),
        position: { x: radii[j] * Math.cos(angle), y: radii[j] * Math.sin(angle) },
      });
    }
  }

  const edges: Edge[] = [];
  const edgeIdByKey = new Map<string, number>();
  let nextEdgeId = 0;

  function getOrCreateEdge(a: number, b: number, assignment: CreaseAssignment): number {
    const key = a < b ? `${a}-${b}` : `${b}-${a}`;
    const existing = edgeIdByKey.get(key);
    if (existing !== undefined) return existing;
    const id = nextEdgeId++;
    edgeIdByKey.set(key, id);
    edges.push({ id, v0: a, v1: b, assignment });
    return id;
  }

  const faces: Face[] = [];
  let nextFaceId = 0;

  // Central polygon face (ring 0).
  {
    const vertexIds = Array.from({ length: n }, (_, i) => vertexId(0, i));
    const edgeIds = Array.from({ length: n }, (_, i) =>
      getOrCreateEdge(vertexId(0, i), vertexId(0, i + 1), ringBoundaryAssignment(0)),
    );
    faces.push({ id: nextFaceId++, vertexIds, edgeIds, ringIndex: 0 });
  }

  // Concentric pleat rings, each split into n quad sectors, each sector split
  // into 2 triangles: T1 = (A0, A1, B0), T2 = (A1, B0, B1).
  for (let j = 1; j <= rings; j++) {
    const innerAssignment = ringBoundaryAssignment(j - 1);
    const outerAssignment: CreaseAssignment = j === rings ? "border" : ringBoundaryAssignment(j);
    const spokeAssignment = radialSpokeAssignment(j);

    for (let i = 0; i < n; i++) {
      const A0 = vertexId(j - 1, i);
      const A1 = vertexId(j - 1, i + 1);
      const B0 = vertexId(j, i);
      const B1 = vertexId(j, i + 1);

      const eA0A1 = getOrCreateEdge(A0, A1, innerAssignment);
      const eB0B1 = getOrCreateEdge(B0, B1, outerAssignment);
      const eA0B0 = getOrCreateEdge(A0, B0, spokeAssignment);
      const eA1B1 = getOrCreateEdge(A1, B1, spokeAssignment);
      const eDiagonal = getOrCreateEdge(A1, B0, "facet");

      faces.push({
        id: nextFaceId++,
        vertexIds: [A0, A1, B0],
        edgeIds: [eA0A1, eDiagonal, eA0B0],
        ringIndex: j,
      });
      faces.push({
        id: nextFaceId++,
        vertexIds: [A1, B0, B1],
        edgeIds: [eDiagonal, eB0B1, eA1B1],
        ringIndex: j,
      });
    }
  }

  // Face adjacency: any two faces sharing an edge id are neighbors.
  const facesByEdge = new Map<number, number[]>();
  for (const face of faces) {
    for (const edgeId of face.edgeIds) {
      const list = facesByEdge.get(edgeId) ?? [];
      list.push(face.id);
      facesByEdge.set(edgeId, list);
    }
  }
  const adjacency: FaceAdjacency[] = faces.map((face) => ({ faceId: face.id, neighbors: [] }));
  for (const [edgeId, faceIds] of facesByEdge) {
    if (faceIds.length !== 2) continue;
    const [fa, fb] = faceIds;
    adjacency[fa].neighbors.push({ faceId: fb, sharedEdgeId: edgeId });
    adjacency[fb].neighbors.push({ faceId: fa, sharedEdgeId: edgeId });
  }

  return { vertices, edges, faces, adjacency, ringCount: rings, sides: n };
}
