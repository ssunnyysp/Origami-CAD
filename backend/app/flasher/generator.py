"""Square flasher crease-pattern generator (Shafer's square-grid flasher; same
family as Lang & Zirbel's deployable-array flashers, specialized to a square
sheet on a unit grid).

A square sheet on an N×N unit-cell grid where N (`grid_divisions`) is ODD.
Odd N gives the sheet a single, well-defined CENTRAL CELL — the hub the rest
of the sheet wraps around: with N cells indexed 0..N-1, the middle index
h = (N-1)/2 is only an integer when N is odd.

The folded ("stowed") state that defines the pattern is a WRAP: the hub cell
stays flat while every other part of the sheet stands up into vertical wall
pleats one grid unit tall wrapped around the hub's perimeter — the whole
sheet collapses toward a ~1×1×1 cube. This is NOT concentric rings (the
mistake a previous version of this generator made — concentric rings with a
small chiral trim can only dome, because nothing in that pattern converts
circumferential sheet length into wall height).

The crease set and every fold's target dihedral below were pinned down by an
ANALYTIC LOOP-CLOSURE ORACLE (fold every face by its exact target angle
along a spanning tree from the hub; a correct pattern makes every vertex's
position agree across all its faces to machine precision, and this one
closes exactly, collapsing to a 1x1x1 box for n=3,5,7). Families, in
hub-centered coordinates, ring bands k=1..m outward, NE-canonical prototypes
(the other three arms/corners are 90° rotations — the pattern is C4,
chirality CCW):

- HUB boundary: mountain, target 90° (the wall folds down from the flat
  hub).
- RING lines (full grid squares at half-integer radii, rl>=2): the
  accordion ridges/troughs, alternating mountain/valley outward, target
  180° — EXCEPT the four "jog" segments where a ring line crosses an
  arm-ladder cell: there the fold has the OPPOSITE gender (the accordion
  phase shifts by one ring across the arm — the signature pinwheel jog of
  every real flasher CP).
- RADIAL grid segments (perpendicular to the near sheet edge): azimuthal
  pleat folds, target 180°, gender alternating with band parity (mountain
  in odd bands). This family is why Shafer's instructions begin "crease an
  N×N grid with every crease both mountained and valleyed".
- RING-CORNER cells (h±k, h±k): one 45° diagonal each, through the cell's
  hub-side corner (main diagonal on the NE/SW corners, anti on NW/SE — the
  pinwheel), target 180°; the cell's ENTERING side edge (south, on the NE
  corner) is a valley at 180° and its EXITING side edge (west, on the NE
  corner) folds only 90° — one of the four true corner bends of the wrap.
- ARM-LADDER cells (NE arm at (h+1, h+k), k=2..m, stepping one cell per
  ring): NO diagonal crease — the arm is a stepped polyline of edge folds:
  west edge 90° (bend), east edge valley 180°, and the jog segments
  described under RING. At k=1 the arm coincides with the corner cell.

Only the 90° folds (hub boundary, corner-exit edges, arm-west edges — the
vertical corner bends of the wrapped box) use fold factor 0.5; every other
crease is a 180°-class pleat (factor 1.0). At mid-fold the bends sit near
45-60° and the pleats near 90-120°: the wrapped-cube state; the exact-180°
endpoint is the pressed-flat stow limit.

Every cell is split into 4 triangles by an X through its center so the mesh
can flex; only the corner-cell halves listed above are real creases, the
rest are "facet" edges (never drawn).

Lang (J. Mechanisms Robotics, 2016) proves an intact flasher sheet is not a
rigid single-DOF mechanism — real paper flashers work because facets flex
slightly. The solver here is exactly that kind of soft, crease-angle-driven
model, so the intact sheet folds the way real paper does.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The hub is a single unit cell; in output coordinates (which are shifted so
# the hub's own center is the origin) its half-width is always 0.5,
# regardless of grid_divisions.
HUB_CENTER = (0.0, 0.0)
HUB_HALF = 0.5


def ring_line_gender(rl: int) -> str:
    """Mountain/valley of ring LINE rl (rl=1 is the hub boundary, counting
    outward). The hub boundary is a mountain (the wall folds down from the
    flat hub); each successive ring line alternates (ridge, trough, ...).
    """
    return "mountain" if rl % 2 == 1 else "valley"


def band_radial_gender(k: int) -> str:
    """Gender of the radial pleat folds in ring band k (band 1 touches the
    hub); alternates because the sheet's colored side faces outward on odd
    bands and inward on even ones."""
    return "mountain" if k % 2 == 1 else "valley"


def band_diagonal_gender(k: int) -> str:
    """Gender of the ring-corner 45° diagonal in band k."""
    if _DIAG_CORNER_ODD == "mountain":
        return "mountain" if k % 2 == 1 else "valley"
    return "valley" if k % 2 == 1 else "mountain"


def _opposite(g: str) -> str:
    return "valley" if g == "mountain" else "mountain"


# The stow-state closure is invariant to the corner-diagonal gender phase
# (the layers coincide either way); the phase below is the one measured to
# fold most cleanly mid-sweep (strain / ring-rotation sync).
_DIAG_CORNER_ODD = "mountain"


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
    # Fraction of the 180° pleat target this crease folds toward at stow:
    # 1.0 for pleat folds, 0.5 for the vertical corner bends of the wrap.
    # Not part of the API contract; consumed by solver.py.
    fold_factor: float = 1.0


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
    m = h  # number of ring bands between the hub and the sheet edge
    center = n / 2.0  # sheet's true center, in 0..n index coordinates

    def rot_ccw(pt: tuple[int, int]) -> tuple[int, int]:
        return (n - pt[1], pt[0])

    def seg_key(p: tuple[int, int], q: tuple[int, int]):
        return (p, q) if p <= q else (q, p)

    # --- special segments (NE prototypes, rotated 4x) -----------------------
    special: dict = {}

    def add_rot4(p: tuple[int, int], q: tuple[int, int], gender: str, factor: float) -> None:
        for _ in range(4):
            special[seg_key(p, q)] = (gender, factor)
            p, q = rot_ccw(p), rot_ccw(q)

    for k in range(1, m + 1):
        # NE ring-corner cell (h+k, h+k): side-edge folds, verified by the
        # loop-closure oracle. Band 1 (the arm-fused corner): entering
        # (south) edge is a 180° valley pleat, exiting (west) edge a 90°
        # bend. Interior corners (2 <= k < m): BOTH side edges are 180°
        # valley pleats. The terminal corner (k = m) ends the sheet with a
        # matched pair of 90° bends — the outermost flap wraps a quarter
        # turn instead of tucking flat (like Lang's choice of terminating a
        # flasher along bend folds). (For m = 2 the terminal corner abuts
        # the arm cell and must keep the interior 180° form.)
        if k == 1:
            c_s, c_w = ("valley", 1.0), (band_radial_gender(1), 0.5)
        elif k < m or m == 2:
            c_s, c_w = ("valley", 1.0), ("valley", 1.0)
        else:
            c_s, c_w = ("mountain", 0.5), ("valley", 0.5)
        add_rot4((h + k, h + k), (h + k + 1, h + k), *c_s)
        add_rot4((h + k, h + k), (h + k, h + k + 1), *c_w)
    for k in range(2, m + 1):
        # NE arm-ladder cell (h+1, h+k): west edge is a 90° bend, east edge a
        # 180° valley pleat (written after the corner entries so it wins the
        # shared segment at k=2 where arm and corner cells are adjacent), and
        # the jogs (south/north edges) fold OPPOSITE to their ring line.
        add_rot4((h + 1, h + k), (h + 1, h + k + 1), band_radial_gender(k), 0.5)
        add_rot4((h + 2, h + k), (h + 2, h + k + 1), "valley", 1.0)
        add_rot4((h + 1, h + k), (h + 2, h + k), _opposite(ring_line_gender(k)), 1.0)
        add_rot4((h + 1, h + k + 1), (h + 2, h + k + 1), _opposite(ring_line_gender(k + 1)), 1.0)

    def grid_segment_assignment(
        p: tuple[int, int], q: tuple[int, int]
    ) -> tuple[str, float]:
        """Classify the unit grid segment p-q (axis-aligned, |p-q|=1).

        Sheet borders are borders; otherwise EVERY grid segment is a crease:
        the special corner/arm segments above, else a ring pleat if the
        segment runs parallel to the near sheet edge (its grid line farther
        from the hub than its position along it), else a radial pleat.
        """
        (x1, y1), (x2, y2) = p, q
        if (x1 in (0, n) and x2 in (0, n)) or (y1 in (0, n) and y2 in (0, n)):
            return ("border", 1.0)
        hit = special.get(seg_key(p, q))
        if hit is not None:
            return hit
        # Hub-centered distances: grid line index g sits at |g - h - 0.5|
        # (a half-integer), the midpoint along the segment at an integer.
        if y1 == y2:  # horizontal segment
            line_d = abs(y1 - (h + 0.5))
            mid_d = abs(min(x1, x2) + 0.5 - (h + 0.5))
        else:  # vertical segment
            line_d = abs(x1 - (h + 0.5))
            mid_d = abs(min(y1, y2) + 0.5 - (h + 0.5))
        if line_d > mid_d:
            rl = int(line_d + 0.5)  # ring line index; rl=1 is the hub edge
            if rl == 1:
                return ("mountain", 0.5)  # hub boundary: 90° wall bend
            return (ring_line_gender(rl), 1.0)
        return (band_radial_gender(int(mid_d)), 1.0)

    # --- diagonal cells: ring corners only, pinwheel orientation ------------
    diag_cells: dict[tuple[int, int], tuple[str, str]] = {}
    for k in range(1, m + 1):
        g = band_diagonal_gender(k)
        diag_cells[(h + k, h + k)] = ("main", g)  # NE
        diag_cells[(h - k, h - k)] = ("main", g)  # SW
        diag_cells[(h - k, h + k)] = ("anti", g)  # NW
        diag_cells[(h + k, h - k)] = ("anti", g)  # SE

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

    def get_or_create_edge(a: int, b: int, assignment: str, factor: float = 1.0) -> int:
        key = (a, b) if a < b else (b, a)
        existing = edge_id_by_key.get(key)
        if existing is not None:
            return existing
        edge_id = len(edges)
        edge_id_by_key[key] = edge_id
        edges.append(Edge(id=edge_id, v0=a, v1=b, assignment=assignment, fold_factor=factor))
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
                v00, v10, *grid_segment_assignment((cx, cy), (cx + 1, cy))
            )
            e_top = get_or_create_edge(
                v01, v11, *grid_segment_assignment((cx, cy + 1), (cx + 1, cy + 1))
            )
            e_left = get_or_create_edge(v00, v01, *grid_segment_assignment((cx, cy), (cx, cy + 1)))
            e_right = get_or_create_edge(
                v10, v11, *grid_segment_assignment((cx + 1, cy), (cx + 1, cy + 1))
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
