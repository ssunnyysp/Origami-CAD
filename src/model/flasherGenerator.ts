import type { CreasePattern, Vertex, Edge, Face, FaceAdjacency, CreaseAssignment } from "./types";

export interface FlasherParams {
  sides: number; // n, number of sides of the central polygon / rotational symmetry order
  rings: number; // k, number of concentric pleat rings around the central polygon
  spiralAngle: number; // radians; angular offset added per ring in the FLAT pattern — makes the arms spiral
  wrapAngle: number; // radians; extra wrap around the hub per ring in the FOLDED state (2π/n = one hub face per ring)
  radiusRatio: number; // > 1, each ring's outer radius = inner radius * radiusRatio
  centralRadius: number; // r0, circumradius of the central polygon in flat-pattern units
}

// Vertex ids encode (ring, sector) so the fold engine can recover both
// without a lookup table. Shared between generator and fold engine.
export function flasherVertexId(sides: number, ring: number, sector: number): number {
  return ring * sides + ((sector % sides) + sides) % sides;
}

export function generateFlasher(params: FlasherParams): CreasePattern {
  const { sides: n, rings, spiralAngle, radiusRatio, centralRadius } = params;

  const vertices: Vertex[] = [];

  // Ring radii: R[0] = centralRadius, R[j] = R[j-1] * radiusRatio.
  const radii: number[] = [centralRadius];
  for (let j = 1; j <= rings; j++) radii.push(radii[j - 1] * radiusRatio);

  // Each ring is rotated by j * spiralAngle relative to the hub, so the
  // "spoke" edges connecting ring j-1 to ring j slant tangentially and chain
  // into n discrete spiral arms — the defining feature of a flasher flat
  // pattern (cf. Guest & Pellegrino's membrane wrap, Lang's flasher).
  for (let j = 0; j <= rings; j++) {
    for (let i = 0; i < n; i++) {
      const angle = (2 * Math.PI * i) / n + j * spiralAngle;
      vertices.push({
        id: flasherVertexId(n, j, i),
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

  // Central polygon face (ring 0). Its boundary is where the wrap begins —
  // mountain, so the arms fold up and around the hub.
  {
    const vertexIds = Array.from({ length: n }, (_, i) => flasherVertexId(n, 0, i));
    const edgeIds = Array.from({ length: n }, (_, i) =>
      getOrCreateEdge(flasherVertexId(n, 0, i), flasherVertexId(n, 0, i + 1), "mountain"),
    );
    faces.push({ id: nextFaceId++, vertexIds, edgeIds, ringIndex: 0 });
  }

  // Concentric pleat rings, each split into n quad sectors, each sector split
  // into 2 triangles: T1 = (A0, A1, B0), T2 = (A1, B0, B1).
  //
  // Crease labeling follows the wrap geometry rather than a flat-foldability
  // proof: the spiral spokes (A0→B0) are the primary wrap creases (mountain),
  // the sector diagonals (A1→B0) take the counter-fold (valley), and the
  // interior ring boundaries bend only gently in the wrapped state (facet).
  for (let j = 1; j <= rings; j++) {
    const innerAssignment: CreaseAssignment = j === 1 ? "mountain" : "facet";
    const outerAssignment: CreaseAssignment = j === rings ? "border" : "facet";

    for (let i = 0; i < n; i++) {
      const A0 = flasherVertexId(n, j - 1, i);
      const A1 = flasherVertexId(n, j - 1, i + 1);
      const B0 = flasherVertexId(n, j, i);
      const B1 = flasherVertexId(n, j, i + 1);

      const eA0A1 = getOrCreateEdge(A0, A1, innerAssignment);
      const eB0B1 = getOrCreateEdge(B0, B1, outerAssignment);
      const eA0B0 = getOrCreateEdge(A0, B0, "mountain");
      const eA1B1 = getOrCreateEdge(A1, B1, "mountain");
      const eDiagonal = getOrCreateEdge(A1, B0, "valley");

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
