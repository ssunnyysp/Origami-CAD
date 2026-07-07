"""Square pinwheel-flasher crease-pattern generator.

This is the classic single-layer flasher (Guest & Pellegrino wrap, the
pattern in every flasher tutorial): a square sheet on an N×N unit grid with
a 1×1 hub cell at the center and 4-fold ROTATIONAL (chiral) symmetry — the
whole pattern is one sector's creases stamped four times, rotated 90° about
the hub center.

Structure per sector (the "north" sector shown; the rest are rotations):

- One 45° diagonal ray per hub corner, all swirling the same direction.
  Two of the four happen to reach sheet corners, two hit edge midspans —
  the pinwheel is deliberately not mirror-symmetric.
- Pleat creases run PERPENDICULAR to the sector's outer edge (radially),
  one per grid line, each hanging from the sheet edge down to the diagonal
  it dies into. Genders alternate by grid parity, so the sheet accordions.
- Crossing a diagonal, a pleat continues as a pleat of the next sector
  rotated 90° — the reverse folds that carry the wrap around the hub
  corners.

Every cell is split into 4 triangles by an X through its center so the mesh
can flex; only X halves lying on the four diagonal rays are real creases,
the rest are "facet" edges (never drawn).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# The hub is the single grid cell [0,1]²; the sheet spans [-m, m].
HUB_CENTER = (0.5, 0.5)
HUB_HALF = 0.5


@dataclass(frozen=True)
class FlasherParams:
    grid_divisions: int  # N; the sheet is N×N unit cells, N even
    wrap_per_ring: float  # square-angle sides of extra wrap per ring at full fold
    layer_gap_ratio: float  # wall-to-wall spacing of the wrapped layers, grid units per ring
    height_ratio: float  # stowed height gained per ring of flat material, grid units


@dataclass
class Vertex:
    id: int
    position: tuple[float, float]  # flat-pattern coordinates


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
    ring_index: int  # taxicab ring about the hub center (0 = hub)


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
        raise ValueError("grid_divisions must be even (the hub sits on the center cell)")
    m = n // 2  # coordinates run -m..m

    # --- crease assignments ------------------------------------------------
    # Grid-line creases, keyed by sorted unit-segment endpoints.
    seg_assignment: dict[tuple[tuple[int, int], tuple[int, int]], str] = {}

    def set_seg(p: tuple[int, int], q: tuple[int, int], assignment: str) -> None:
        key = (p, q) if p <= q else (q, p)
        seg_assignment.setdefault(key, assignment)

    # Hub boundary: the wrap starts here.
    hub = [(0, 0), (1, 0), (1, 1), (0, 1)]
    for i in range(4):
        set_seg(hub[i], hub[(i + 1) % 4], "mountain")

    # Pleats, one sector per sheet edge, each pleat running from the diagonal
    # it dies into out to its sector's edge. The north/east sectors are
    # bounded inward by max(k, 1-k) (the NE/NW and NE/SE rays), the south/
    # west sectors by min(k, 1-k). A pleat keeps its gender as it turns a
    # hub corner — the wall crease of the wrap is continuous — so gender is
    # a function of grid parity alone.
    for k in range(-(m - 1), m):
        gender = "mountain" if k % 2 == 0 else "valley"
        near = max(k, 1 - k)  # inner end against the upper/right diagonals
        far = min(k, 1 - k)  # inner end against the lower/left diagonals

        for y in range(near, m):  # north: vertical pleat x = k
            set_seg((k, y), (k, y + 1), gender)
        for y in range(-m, far):  # south: vertical pleat x = k
            set_seg((k, y), (k, y + 1), gender)
        for x in range(near, m):  # east: horizontal pleat y = k
            set_seg((x, k), (x + 1, k), gender)
        for x in range(-m, far):  # west: horizontal pleat y = k
            set_seg((x, k), (x + 1, k), gender)

    # Diagonal rays through cell X's: (t, t) main-diagonal cells for the NE
    # ray and its three rotations. Gender alternates along each ray — the
    # corner reverse-folds flip every layer of the wrap.
    diag_cells: dict[tuple[int, int], tuple[str, str]] = {}  # cell -> (which, gender)
    for t in range(1, m):
        gender = "mountain" if t % 2 == 1 else "valley"
        diag_cells[(t, t)] = ("main", gender)
        diag_cells[(t, -t)] = ("anti", gender)
        diag_cells[(-t, -t)] = ("main", gender)
        diag_cells[(-t, t)] = ("anti", gender)

    def grid_segment_assignment(p: tuple[int, int], q: tuple[int, int]) -> str:
        (x1, y1), (x2, y2) = p, q
        if (abs(x1) == m and abs(x2) == m) or (abs(y1) == m and abs(y2) == m):
            return "border"
        key = (p, q) if p <= q else (q, p)
        return seg_assignment.get(key, "facet")

    # --- mesh --------------------------------------------------------------
    grid_stride = n + 1

    def grid_id(x: int, y: int) -> int:
        return (y + m) * grid_stride + (x + m)

    def center_id(cx: int, cy: int) -> int:
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

    faces: list[Face] = []

    for cy in range(-m, m):
        for cx in range(-m, m):
            v00 = grid_id(cx, cy)
            v10 = grid_id(cx + 1, cy)
            v11 = grid_id(cx + 1, cy + 1)
            v01 = grid_id(cx, cy + 1)
            vc = center_id(cx, cy)

            main_half = cross_half = "facet"
            diag = diag_cells.get((cx, cy))
            if diag is not None:
                which, gender = diag
                if which == "main":
                    main_half = gender
                else:
                    cross_half = gender

            e_bottom = get_or_create_edge(
                v00, v10, grid_segment_assignment((cx, cy), (cx + 1, cy))
            )
            e_top = get_or_create_edge(
                v01, v11, grid_segment_assignment((cx, cy + 1), (cx + 1, cy + 1))
            )
            e_left = get_or_create_edge(v00, v01, grid_segment_assignment((cx, cy), (cx, cy + 1)))
            e_right = get_or_create_edge(
                v10, v11, grid_segment_assignment((cx + 1, cy), (cx + 1, cy + 1))
            )
            e_00c = get_or_create_edge(v00, vc, main_half)
            e_11c = get_or_create_edge(v11, vc, main_half)
            e_10c = get_or_create_edge(v10, vc, cross_half)
            e_01c = get_or_create_edge(v01, vc, cross_half)

            cell_ring = max(abs(cx + 0.5 - HUB_CENTER[0]), abs(cy + 0.5 - HUB_CENTER[1]))
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
