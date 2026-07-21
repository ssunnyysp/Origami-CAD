"""Square WRAP-PINWHEEL flasher crease-pattern generator.

A square sheet on an N×N unit-cell grid where N (`grid_divisions`) is ODD.
Odd N gives the sheet a single, well-defined CENTRAL CELL — the hub the rest
of the sheet wraps around: with N cells indexed 0..N-1, the middle index
h = (N-1)/2 is only an integer when N is odd.

THE PATTERN (this is the hand-authored design the project's author folds in
real life, not a procedural ring pattern — an earlier version of this module
generated concentric ring/arm-ladder creases and is preserved only in git
history). The sheet is quartered into four congruent RECTANGULAR regions
arranged as a C4 pinwheel about the hub:

    +---------+-------+
    |    R1   |       |          hub = the single center cell (stays flat)
    |  (NW)   |  R2   |          R1: cx 0..h-1,  cy h..N-1
    +-----+---+ (NE)  |          R2: cx h..N-1,  cy h+1..N-1
    |     |hub+-------+          R3: cx h+1..N-1, cy 0..h
    | R4  +---+   R3  |          R4: cx 0..h,    cy 0..h-1
    | (SW)|       (SE)|          (each is h×(h+1); they tile the sheet minus
    +-----+-----------+           the hub, with 90° rotational symmetry)

Only the NW region's creases are written out as a prototype; the other three
are exact 90° rotations of it (see `rot_seg` / `set_cell4`). Within each
region:

- DIAGONAL: a single 45° crease runs from just off the hub corner out toward
  the sheet corner, h cells long (cells (h-1-k, h+k) for k=0..h-1 in the NW
  region). It splits the region into a hub-side triangle and an outer
  triangle. The rotation makes the four diagonals a pinwheel.
- ACCORDION PLEATS fill the HUB-SIDE triangle as a staircase of horizontal
  and vertical grid folds, gender alternating mountain/valley with taxicab
  distance from the hub (mountain nearest the hub). These are the folds that
  compress as the sheet stows.
- The OUTER triangle (beyond the diagonal) carries NO creases — it stays a
  flat facet flap that WRAPS around the hub as the accordion compresses.
  This is the "wraps around the hub instead of crumpling" behavior.
- HUB boundary: the four edges of the hub cell fold ~90° (the walls stand up
  from the flat hub).

Fold factors: the hub-boundary bends use 0.5 (→ ~90° at stow); every marked
pleat and diagonal is a 180°-class fold (factor 1.0). Every cell is split
into 4 triangles by an X through its center so the mesh can flex; only the
marked halves/edges above are real creases, the rest are "facet" edges.

Unlike the earlier ring pattern, this pinwheel does NOT rigidly close to an
exact 1×1×1 box (a 45° diagonal cannot span the non-square h×(h+1) region
corner-to-corner, so a rigid loop-closure oracle leaves a small residual).
That is fine and expected: Lang (J. Mechanisms Robotics, 2016) proves an
intact flasher sheet is not a rigid single-DOF mechanism — real paper
flashers work because the facets flex. The solver here is exactly that kind
of soft, crease-angle-driven model, so the intact sheet wraps the way real
paper does; small grids (7×7) wrap cleanly, the larger presets wrap less
tightly within the solver's time budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The hub is a single unit cell; in output coordinates (which are shifted so
# the hub's own center is the origin) its half-width is always 0.5,
# regardless of grid_divisions.
HUB_CENTER = (0.0, 0.0)
HUB_HALF = 0.5


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
    m = h  # rings out from the hub to the sheet edge (kept as CreasePattern.ring_count)
    center = n / 2.0  # sheet's true center, in 0..n index coordinates

    def seg_key(p: tuple[int, int], q: tuple[int, int]):
        return (p, q) if p <= q else (q, p)

    # --- WRAP PINWHEEL pattern (user-authored, see module docstring) --------
    # The sheet is quartered into four congruent rectangular regions arranged
    # as a pinwheel about the hub. Each region is split by a single 45°
    # diagonal running from just off the hub corner out to just short of the
    # sheet corner; the HUB-SIDE triangle of that split is packed with an
    # accordion of horizontal/vertical grid pleats (a triangular staircase),
    # while the OUTER triangle stays a facet flap that wraps around the hub as
    # the accordion compresses. The whole thing is C4: only the NW region's
    # prototype is written out, then rotated 90° three times (segments and
    # cells alike) so the four regions match exactly.

    def rot_seg(t: str, x: int, y: int) -> tuple[str, int, int]:
        # 90° CCW image (endpoints map (x, y) -> (n - y, x)) of a unit grid
        # segment keyed by ("H"|"V", min-x, min-y): an H run maps to a V run.
        return ("V", n - y, x) if t == "H" else ("H", n - y - 1, x)

    # Accordion pleat lines of the NW region's hub-side triangle, mirrored x4.
    foldlines: dict[tuple[str, int, int], str] = {}

    def set_seg4(t: str, x: int, y: int, gender: str) -> None:
        seg = (t, x, y)
        for _ in range(4):
            foldlines[seg] = gender
            seg = rot_seg(*seg)

    for ry in range(h):  # horizontal pleats: row h+ry, columns 0..h-1-ry
        g = "mountain" if ry % 2 == 0 else "valley"
        for x in range(0, h - ry):
            set_seg4("H", x, h + ry, g)
    for rx in range(h):  # vertical pleats: column h-rx, rows h+rx..n-2
        g = "mountain" if rx % 2 == 0 else "valley"
        for y in range(h + rx, n - 1):
            set_seg4("V", h - rx, y, g)

    # The four region diagonals: NW region's anti-diagonal cells, mirrored x4
    # (a 90° cell rotation flips main<->anti, giving the pinwheel chirality).
    diag_cells: dict[tuple[int, int], tuple[str, str]] = {}

    def set_cell4(cx: int, cy: int, which: str, gender: str) -> None:
        for _ in range(4):
            diag_cells[(cx, cy)] = (which, gender)
            cx, cy, which = n - cy - 1, cx, ("main" if which == "anti" else "anti")

    for k in range(h):  # NW diagonal cells (h-1-k, h+k), out from the hub
        set_cell4(h - 1 - k, h + k, "anti", "mountain")

    hub_edges = {
        seg_key((h, h), (h + 1, h)),
        seg_key((h, h + 1), (h + 1, h + 1)),
        seg_key((h, h), (h, h + 1)),
        seg_key((h + 1, h), (h + 1, h + 1)),
    }

    def grid_segment_assignment(
        p: tuple[int, int], q: tuple[int, int]
    ) -> tuple[str, float]:
        """Classify the unit grid segment p-q (axis-aligned, |p-q|=1).

        Sheet edge -> border; the four hub-cell edges -> 90° wall bends; a
        marked accordion pleat -> full 180° fold of its gender; everything
        else (the outer wrap flaps) -> uncreased facet.
        """
        (x1, y1), (x2, y2) = p, q
        if (x1 in (0, n) and x2 in (0, n)) or (y1 in (0, n) and y2 in (0, n)):
            return ("border", 1.0)
        if seg_key(p, q) in hub_edges:
            return ("mountain", 0.5)  # hub boundary: 90° wall bend
        seg = ("H", min(x1, x2), y1) if y1 == y2 else ("V", x1, min(y1, y2))
        gender = foldlines.get(seg)
        if gender is None:
            return ("facet", 1.0)
        return (gender, 1.0)

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
