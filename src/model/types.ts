// Custom crease-pattern data model (not the FOLD format — this app generates
// patterns parametrically rather than importing authored files).

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
