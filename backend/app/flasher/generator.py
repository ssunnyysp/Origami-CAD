"""Square flasher crease-pattern generator (Shafer / Zirbel & Lang style, as
in the ORI*botics "natural folding" diagram and Shafer's "Flasher Big Bang").

A square sheet on an N×N unit-cell grid where N (`grid_divisions`) is ODD.
Odd N is what gives the sheet a single, well-defined CENTRAL CELL — the hub
everything folds around: with N cells indexed 0..N-1, the middle index
h = (N-1)/2 is only an integer when N is odd. An even N splits the center
between four cells with no true middle, which is exactly the bug an even
grid had here before.

Structure, all centered on the hub cell (whose own center sits at the
sheet's true geometric origin (0, 0) in the output coordinates):

- The hub cell itself stays flat and rigid — the "polygon" of "natural
  folding: rotation of a polygon on a sheet". Its boundary is the first
  mountain crease.
- Two full corner-to-corner diagonals, passing exactly through the hub's
  center, continue outward from its corners — the reverse folds that carry
  each ring around a hub corner.
- Ring pleats run PARALLEL to each edge at every grid line beyond the hub,
  forming simple concentric squares (not spokes), alternating mountain and
  valley outward.
- Folding is "natural folding": the hub stays flat, colored side up, while
  the sheet accordions vertically between the valley rings (hub-plane
  troughs) and mountain rings (wall ridges) as it coils around the hub,
  collapsing into a compact block one band tall centered on the hub.

Every cell is split into 4 triangles by an X through its center so the mesh
can flex; only X halves lying on the two diagonals are real creases, the
rest are "facet" edges (never drawn).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# The hub is a single unit cell; in output coordinates (which are shifted so
# the hub's own center is the origin) its half-width is always 0.5,
# regardless of grid_divisions.
HUB_CENTER = (0.0, 0.0)
HUB_HALF = 0.5


def ring_gender(k: int) -> str:
    """Mountain/valley of ring k's own boundary crease (k=1 touches the hub,
    alternating outward). solver.py folds each crease by the angle read
    straight off this pattern's edge assignments, so the fold can never
    silently drift from the drawn pattern.
    """
    return "mountain" if k % 2 == 1 else "valley"


@dataclass(frozen=True)
class FlasherParams:
    grid_divisions: int  # N; the sheet is N×N unit cells, N odd (single center cell)
    layer_gap_ratio: float  # wall-to-wall spacing of the wrapped layers, grid units per ring
    height_ratio: float  # stowed height gained per ring of flat material, grid units


@dataclass
class Vertex:
    id: int
    position: tuple[float, float]  # flat-pattern coordinates, hub center at origin


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
    ring_index: int  # taxicab ring about the hub (0 = hub)


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
    if n % 2 != 1:
        raise ValueError(
            "grid_divisions must be odd, so the sheet has a single, well-centered "
            "hub cell (an even count splits the center between four cells)"
        )
    h = (n - 1) // 2  # index of the hub cell (both x and y)
    m = h  # number of pleat rings between the hub and the sheet edge
    center = n / 2.0  # sheet's true center, in 0..n index coordinates

    # Ring k's square boundary spans index range [low(k), high(k)]; k=0 is
    # the hub cell's own boundary, k=1..m are the pleat rings outward.
    def low(k: int) -> int:
        return h - k

    def high(k: int) -> int:
        return h + 1 + k

    # --- crease assignments ------------------------------------------------
    # Grid-line creases, keyed by sorted unit-segment endpoints (in 0..n
    # index coordinates).
    seg_assignment: dict[tuple[tuple[int, int], tuple[int, int]], str] = {}

    def set_seg(p: tuple[int, int], q: tuple[int, int], assignment: str) -> None:
        key = (p, q) if p <= q else (q, p)
        seg_assignment.setdefault(key, assignment)

    # Hub boundary (ring 0): the first mountain — the wall of the wrap begins
    # here.
    lo, hi = low(0), high(0)
    hub = [(lo, lo), (hi, lo), (hi, hi), (lo, hi)]
    for i in range(4):
        set_seg(hub[i], hub[(i + 1) % 4], "mountain")

    # Ring pleats k=1..m: each ring's 4 sides are trimmed one unit short at a
    # consistently-rotated (CCW) corner and rejoined there by a diagonal cut
    # (below). That single consistent trim/cut is what gives the pattern a
    # CHIRALITY — a fixed handedness — instead of the mirror-symmetric plain
    # square rings this generator used to draw. A mirror-symmetric pattern
    # has no preferred turning direction, so folding it only domes; a chiral
    # one lets every ring rotate the SAME way around the hub simultaneously,
    # the real flasher twist motion.
    for k in range(1, m + 1):
        lo, hi = low(k), high(k)
        gender = ring_gender(k)
        for x in range(lo, hi - 1):
            set_seg((x, hi), (x + 1, hi), gender)  # top, trimmed at right (NE) end
        for y in range(lo + 1, hi):
            set_seg((hi, y), (hi, y + 1), gender)  # right, trimmed at bottom (SE) end
        for x in range(lo + 1, hi):
            set_seg((x, lo), (x + 1, lo), gender)  # bottom, trimmed at left (SW) end
        for y in range(lo, hi - 1):
            set_seg((lo, y), (lo, y + 1), gender)  # left, trimmed at top (NW) end

    # Chiral corner cuts: the unit cell at each trimmed corner is split by ONE
    # diagonal (not the symmetric X the old generator drew), so it both closes
    # the gap left by the trim AND turns the boundary — every corner turns the
    # same rotational way, which is what gives the pattern a fixed handedness.
    diag_cells: dict[tuple[int, int], tuple[str, str]] = {}  # cell -> (which, gender)
    for k in range(1, m + 1):
        lo, hi = low(k), high(k)
        ring_g = ring_gender(k)
        # The corner cut is the OPPOSITE gender from the ring's own boundary —
        # it is a genderless (in Shafer's sense) reverse fold, and using the
        # opposite sense is what keeps every corner turning the SAME
        # rotational way. Using the same gender as the boundary (this
        # generator's earlier bug) makes alternating rings twist in opposite
        # directions instead of rotating together.
        diag_g = "valley" if ring_g == "mountain" else "mountain"
        diag_cells[(hi - 1, hi - 1)] = ("main", diag_g)  # NE gap
        diag_cells[(hi - 1, lo)] = ("anti", diag_g)  # SE gap
        diag_cells[(lo, lo)] = ("main", diag_g)  # SW gap
        diag_cells[(lo, hi - 1)] = ("anti", diag_g)  # NW gap

    def grid_segment_assignment(p: tuple[int, int], q: tuple[int, int]) -> str:
        (x1, y1), (x2, y2) = p, q
        if (x1 in (0, n) and x2 in (0, n)) or (y1 in (0, n) and y2 in (0, n)):
            return "border"
        key = (p, q) if p <= q else (q, p)
        return seg_assignment.get(key, "facet")

    # --- mesh --------------------------------------------------------------
    # Index coordinates run 0..n for the mesh arrays; output positions are
    # shifted by `center` so the hub cell's own center is the origin.
    grid_stride = n + 1

    def grid_id(x: int, y: int) -> int:
        return y * grid_stride + x

    def center_id(cx: int, cy: int) -> int:
        return grid_stride * grid_stride + cy * n + cx

    vertices: list[Vertex] = []
    for y in range(n + 1):
        for x in range(n + 1):
            vertices.append(Vertex(id=grid_id(x, y), position=(x - center, y - center)))
    for cy in range(n):
        for cx in range(n):
            vertices.append(
                Vertex(id=center_id(cx, cy), position=(cx + 0.5 - center, cy + 0.5 - center))
            )

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

    for cy in range(n):
        for cx in range(n):
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

            cell_ring = max(abs(cx - h), abs(cy - h))
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
                        ring_index=cell_ring,
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
