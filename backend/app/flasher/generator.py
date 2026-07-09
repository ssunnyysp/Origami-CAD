"""Square flasher crease-pattern generator (Zirbel & Lang 2013 style, as in
the ORI*botics "natural folding" diagram).

A square sheet on an N×N unit grid with a 1×1 hub cell at the center and
4-fold ROTATIONAL (chiral) symmetry:

- One 45° diagonal ray per hub corner, all swirling the same direction —
  the corner folds that carry the wrap around the hub's corners.
- Ring pleats run PARALLEL to each sector's outer edge at every grid line,
  spanning ray to ray. The pinwheel offset chains them into two square
  spirals: a mountain spiral (the wrapped wall's top ridges) and a valley
  spiral (its bottom troughs), half a band apart.
- Folding is "natural folding — rotation of a polygon on a sheet": the hub
  stays flat (colored side up) and the sheet accordions vertically between
  the valley and mountain spirals while coiling around the hub, collapsing
  into a compact block one band tall.

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

    # Spiral ring pleats (Zirbel & Lang style, cf. the ORI*botics diagram):
    # in each sector, creases run PARALLEL to the sector's edge at integer
    # grid lines, spanning between the two diagonal rays that bound the
    # sector. Because the rays swirl pinwheel-fashion, ring segments of
    # adjacent sectors meet offset by one unit — the mountain lines chain
    # into one square spiral, the valleys into another, half a band apart.
    #
    # Gender by distance d from the hub edge: the sheet lies flat on the hub
    # plane at even rings and rises to the wrapped wall's ridge at odd rings,
    # so even rings (including the hub boundary, d = 0) are valleys and odd
    # rings are mountains.
    for j in range(-(m - 1), m):
        if j >= 1:
            d = j - 1
            gender = "mountain" if d % 2 == 1 else "valley"
            for x in range(max(1 - j, -m), min(j, m)):  # north: y = j
                set_seg((x, j), (x + 1, j), gender)
            for y in range(max(1 - j, -m), min(j, m)):  # east: x = j
                set_seg((j, y), (j, y + 1), gender)
        else:
            d = -j
            gender = "mountain" if d % 2 == 1 else "valley"
            for x in range(max(j, -m), min(1 - j, m)):  # south: y = j
                set_seg((x, j), (x + 1, j), gender)
            for y in range(max(j, -m), min(1 - j, m)):  # west: x = j
                set_seg((j, y), (j, y + 1), gender)

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
