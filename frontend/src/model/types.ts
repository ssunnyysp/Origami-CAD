// Custom crease-pattern data model (not the FOLD format — this app generates
// patterns parametrically rather than importing authored files).
//
// These types are the API contract with the Python backend: the JSON returned
// by /api/presets and /api/flasher/geometry deserializes directly into them.

export interface Point2D {
  x: number;
  y: number;
}

export type CreaseAssignment = "mountain" | "valley" | "border" | "facet";

export interface Vertex {
  id: number;
  position: Point2D; // flat-pattern coordinates
}

export interface Edge {
  id: number;
  v0: number; // vertex id
  v1: number; // vertex id
  assignment: CreaseAssignment;
}

export interface Face {
  id: number;
  vertexIds: number[]; // ordered, CCW in the flat pattern; triangles only for now
  edgeIds: number[]; // edges bounding this face, same winding order as vertexIds
  ringIndex: number; // which concentric ring this face belongs to (0 = central polygon)
}

// Face-adjacency spanning-tree data, kept even though the current fold engine
// only needs ringIndex — lets a future per-hinge rigid solver reuse this
// structure without changing the data model.
export interface FaceAdjacency {
  faceId: number;
  neighbors: { faceId: number; sharedEdgeId: number }[];
}

export interface CreasePattern {
  vertices: Vertex[];
  edges: Edge[];
  faces: Face[];
  adjacency: FaceAdjacency[];
  ringCount: number; // k, number of concentric pleat rings (excluding the central polygon)
  sides: number; // n
}

// Square-flasher parameters. The sheet is always a square, gridDivisions×
// gridDivisions unit cells around a central 2×2 hub. Body of
// POST /api/flasher/geometry.
export interface FlasherParams {
  gridDivisions: number; // N, even; Shafer's Big Bang uses 32
  wrapPerRing: number; // square-angle sides of extra wrap per ring at full fold
  layerGapRatio: number; // spacing of the wrapped layers, grid units per ring
  heightRatio: number; // stowed height gained per ring of flat material
}

export interface FlasherPreset extends FlasherParams {
  id: string;
  name: string;
  paperColor: string;
  roughness: number;
  metalness: number;
}

// Response of POST /api/flasher/geometry: the crease pattern plus the fold
// trajectory solved server-side as one 0→1 sweep. frames[k] holds xyz triples
// (indexed by vertex id) at foldnessSamples[k]; the client lerps between
// adjacent frames for arbitrary foldness values, so animation never needs a
// network round trip.
export interface FlasherGeometry {
  pattern: CreasePattern;
  foldnessSamples: number[];
  frames: number[][];
}
