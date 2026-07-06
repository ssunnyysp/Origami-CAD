"""Square-grid flasher crease-pattern generator (Shafer / Lang style).

The sheet is always a SQUARE, divided into an N×N unit grid around a central
2×2 hub square. The crease structure follows the classic flasher:

- The two main diagonals split the sheet into 4 triangular quadrants.
- In each quadrant, the grid lines PARALLEL to the near sheet edge are the
  pleat creases ("ring" lines), alternating mountain/valley by ring parity.
- Crossing a diagonal into the next quadrant flips every ring line's gender
  (Shafer: "every crease should get mountained and valleyed"). This
  per-quadrant flip is what makes the collapse a spiral wrap around the hub
  rather than a flat twist fold.
- Every cell is split into 4 triangles by an X through its center. In cells
  along the main diagonals the X halves are real creases (the reverse folds
  that turn a pleat 90° around the hub corner); elsewhere they are "facet"
  edges — triangulation only, never drawn.

Grid lines perpendicular to a quadrant's pleats are "facet" too: they exist
in the mesh but are not creases of the pattern.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

HUB_HALF = 1.0  # half-size of the central hub square, in grid units


@dataclass(frozen=True)
class FlasherParams:
    grid_divisions: int  # N; the sheet is N×N unit cells, N even
    wrap_per_ring: float  # square-angle sides of extra wrap per ring at full fold
    layer_gap_ratio: float  # wall-to-wall spacing of the wrapped layers, grid units per ring
    height_ratio: float  # stowed height gained per ring of flat material, grid units


@dataclass
class Vertex:
    id: int
    position: tuple[float, float]  # flat-pattern coordinates, sheet center at origin


@dataclass
class Edge:
    id: int
    v0: int
    v1: int
    assignment: str  # "mountain" | "valley" | "border" | "facet"


@dataclass
class Face:
    id: int
    vertex_ids: list[int]  # ordered CCW in the flat pattern
    edge_ids: list[int]  # same winding order
    ring_index: int  # taxicab ring this face belongs to (0 = hub)


@dataclass
class CreasePattern:
    vertices: list[Vertex]
    edges: list[Edge]
    faces: list[Face]
    adjacency: list[dict] = field(default_factory=list)
    ring_count: int = 0
    sides: int = 4  # always square paper


def generate_flasher(params: FlasherParams) -> CreasePattern:
    n = params.grid_divisions
    if n % 2 != 0:
        raise ValueError("grid_divisions must be even (hub sits on the center lines)")
    m = n // 2  # coordinates run -m..m

    grid_stride = n + 1

    def grid_id(x: int, y: int) -> int:
        return (y + m) * grid_stride + (x + m)

    def center_id(cx: int, cy: int) -> int:
        # cell (cx, cy) spans [cx, cx+1] × [cy, cy+1]; cx, cy in [-m, m-1]
        return grid_stride * grid_stride + (cy + m) * n + (cx + m)

    vertices: list[Vertex] = []
    for y in range(-m, m + 1):
        for x in range(-m, m + 1):
            vertices.append(Vertex(id=grid_id(x, y), position=(float(x), float(y))))
    for cy in range(-m, m):
        for cx in range(-m, m):
            vertices.append(Vertex(id=center_id(cx, cy), position=(cx + 0.5, cy + 0.5)))

    edges: list[Edge] = []
    edge_id_by_key: dict[tuple[int, int], int] = {}

    def get_or_create_edge(a: int, b: int, assignment: str) -> int:
        key = (a, b) if a < b else (b, a)
        existing = edge_id_by_key.get(key)
        if existing is not None:
            return existing
        edge_id = len(edges)
        edge_id_by_key[key] = edge_id
        edges.append(Edge(id=edge_id, v0=a, v1=b, assignment=assignment))
        return edge_id

    def ring_gender(ring: int, quadrant: int) -> str:
        # Gender flips every quadrant (the spiral) and every ring (the pleats).
        return "mountain" if (ring + quadrant) % 2 == 0 else "valley"

    def horizontal_assignment(x: int, k: int) -> str:
        """Grid segment from (x, k) to (x+1, k)."""
        if abs(k) == m:
            return "border"
        # Pleat crease only where the segment lies on taxicab ring |k| — i.e.
        # inside the top (k>0) or bottom (k<0) quadrant. Elsewhere it runs
        # radially and is just mesh structure.
        if k != 0 and max(abs(x), abs(x + 1)) <= abs(k):
            return ring_gender(abs(k), 1 if k > 0 else 3)
        return "facet"

    def vertical_assignment(j: int, y: int) -> str:
        """Grid segment from (j, y) to (j, y+1)."""
        if abs(j) == m:
            return "border"
        if j != 0 and max(abs(y), abs(y + 1)) <= abs(j):
            return ring_gender(abs(j), 0 if j > 0 else 2)
        return "facet"

    faces: list[Face] = []

    for cy in range(-m, m):
        for cx in range(-m, m):
            v00 = grid_id(cx, cy)
            v10 = grid_id(cx + 1, cy)
            v11 = grid_id(cx + 1, cy + 1)
            v01 = grid_id(cx, cy + 1)
            vc = center_id(cx, cy)

            cell_ring = max(abs(cx + 0.5), abs(cy + 0.5))  # taxicab radius of cell center

            # X assignments: real creases only in cells the sheet diagonals
            # pass through (and outside the hub). The half-diagonals ON the
            # sheet diagonal carry one gender; the crossing pair carries the
            # opposite — the reverse-fold detail of the flasher.
            on_main_diag = cx == cy  # sheet diagonal y = x runs v00 → vc → v11
            on_anti_diag = cy == -cx - 1  # sheet diagonal y = -x runs v10 → vc → v01
            main_half = cross_half = "facet"
            if cell_ring > HUB_HALF and (on_main_diag or on_anti_diag):
                k = int(cell_ring + 0.5)
                diag_gender = "mountain" if k % 2 == 0 else "valley"
                reverse_gender = "valley" if k % 2 == 0 else "mountain"
                if on_main_diag:
                    main_half, cross_half = diag_gender, reverse_gender
                else:
                    main_half, cross_half = reverse_gender, diag_gender

            e_bottom = get_or_create_edge(v00, v10, horizontal_assignment(cx, cy))
            e_top = get_or_create_edge(v01, v11, horizontal_assignment(cx, cy + 1))
            e_left = get_or_create_edge(v00, v01, vertical_assignment(cx, cy))
            e_right = get_or_create_edge(v10, v11, vertical_assignment(cx + 1, cy))
            e_00c = get_or_create_edge(v00, vc, main_half)
            e_11c = get_or_create_edge(v11, vc, main_half)
            e_10c = get_or_create_edge(v10, vc, cross_half)
            e_01c = get_or_create_edge(v01, vc, cross_half)

            ring_index = int(math.ceil(cell_ring))
            for tri_vertices, tri_edges in (
                ([v00, v10, vc], [e_bottom, e_10c, e_00c]),
                ([v10, v11, vc], [e_right, e_11c, e_10c]),
                ([v11, v01, vc], [e_top, e_01c, e_11c]),
                ([v01, v00, vc], [e_left, e_00c, e_01c]),
            ):
                faces.append(
                    Face(
                        id=len(faces),
                        vertex_ids=tri_vertices,
                        edge_ids=tri_edges,
                        ring_index=ring_index,
                    )
                )

    # Face adjacency: any two faces sharing an edge id are neighbors.
    faces_by_edge: dict[int, list[int]] = {}
    for face in faces:
        for edge_id in face.edge_ids:
            faces_by_edge.setdefault(edge_id, []).append(face.id)
    adjacency = [{"faceId": face.id, "neighbors": []} for face in faces]
    for edge_id, face_ids in faces_by_edge.items():
        if len(face_ids) != 2:
            continue
        fa, fb = face_ids
        adjacency[fa]["neighbors"].append({"faceId": fb, "sharedEdgeId": edge_id})
        adjacency[fb]["neighbors"].append({"faceId": fa, "sharedEdgeId": edge_id})

    return CreasePattern(
        vertices=vertices,
        edges=edges,
        faces=faces,
        adjacency=adjacency,
        ring_count=m,
        sides=4,
    )
