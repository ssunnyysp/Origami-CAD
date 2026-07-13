"""Square flasher crease-pattern generator — central square pivot, concentric
twisted rings, crossed spokes.

## Two designs that were tried and measured to be non-rigid-foldable

**Design 1** (diagonal reverse-fold at trimmed/untrimmed corners): every
ring's four sides run corner-to-corner, with a single reverse-fold diagonal
cut at each corner. Measuring the actual creases meeting at the hub's own
corner found exactly THREE real creases: two hub-boundary mountains
(perpendicular) plus one diagonal valley. Maekawa's theorem requires
mountain-count minus valley-count to be even at every interior vertex
(it equals degree − 2·valley-count, so it shares degree's parity); three
creases can never satisfy that. A degree-3 vertex is a spherical 3-bar
linkage, which — like a rigid triangle under SSS — has zero internal
degrees of freedom for generic side lengths (this pattern's actual sector
angles were measured to be 171.1°/98.9°/90°, not the special degenerate
case that would allow motion). It cannot rigidly fold at all.

**Design 2** (single straight spoke per ring corner, this file's first
version): ring k's corner i connects to ring (k−1)'s corner i by one
radial spoke; this DOES give interior ring corners (0 < k < rings) proper
degree 4 with mountain−valley = ±2 (provable: the two circumferential
creases share a sign, and spoke_gender(k,i) is always the opposite of
spoke_gender(k+1,i)). But it reproduces the exact same degree-3 problem at
the hub's own corners (hub's 2 boundary creases + 1 outward spoke = 3),
because the hub has no "ring −1" to supply a matching inward spoke.
Measured directly: 8 of 12 crease-pattern vertices failed Maekawa on a
5×5-equivalent grid, all of them at the hub or the outermost ring.

## This design: crossed spokes

Between ring k−1 and ring k, panel i (spanning corner i to i+1) is the
quadrilateral `C[k-1][i], C[k-1][i+1], C[k][i+1], C[k][i]`. Instead of
leaving this panel's diagonal as an uncreased ("facet") triangulation seam,
it is a REAL crease — `cross_gender(k, i+1)`, connecting `C[k-1][i+1]` to
`C[k][i]` — so each ring transition contributes TWO spoke-type creases per
corner instead of one: a straight spoke `spoke_gender(k, i)` (shared
between panel i−1 and panel i) and a crossed spoke (the diagonal of
panel i+1, reaching back to touch corner i).

This changes every corner's degree:
- **Hub corner i** (k=0): 2 boundary creases + spokes to ring 1's corners i
  and i−1 (the straight spoke of panel i, and the crossed spoke of panel
  i+1, which both touch hub corner i) = degree 4.
- **Interior ring corner i** (0 < k < rings): 2 circumferential (ring k's
  own boundary) + 2 inward (straight spoke(k,i), crossed spoke(k,i+1)) + 2
  outward (straight spoke(k+1,i), crossed spoke(k+1,i)) = degree 6.
- **Outermost ring corner** (k = rings): the outer boundary is the sheet's
  physical edge (not a crease), so only the 2 inward spoke-type creases
  meet there — a boundary-adjacent vertex, which (like the outer corners of
  any cut sheet) does not need to satisfy Maekawa, since the paper does not
  wrap a full 360° around it.

`spoke_gender`/`cross_gender`'s docstrings give the parity argument for why
every interior vertex (hub and true interior rings alike) measures
mountain−valley = ±2 unconditionally; `scripts/validate_flasher.py` checks
this directly against the generated pattern (not just trusts the proof)
before any folding is attempted, exactly because the two earlier designs
looked reasonable on paper and were only caught by direct measurement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

HUB_CENTER = (0.0, 0.0)
HUB_APOTHEM = 0.5  # half-width of the single central hub cell (grid units)
SIDES = 4  # the paper is always square
PLEAT_WIDTH = 1.0  # one grid unit per ring, so ring count matches (N-1)/2
TWIST_RATIO = 0.55  # twist per ring, as a fraction of pi/SIDES — tuned via
# scripts/validate_flasher.py (see PR description for the sweep); any value
# in (0, 1) keeps the pattern chiral.


def ring_gender(k: int) -> str:
    """Mountain/valley of ring k's own circumferential boundary crease.
    k=0 is the hub's own boundary (always mountain), alternating outward."""
    if k == 0:
        return "mountain"
    return "mountain" if k % 2 == 1 else "valley"


def _opposite(gender: str) -> str:
    return "valley" if gender == "mountain" else "mountain"


def spoke_gender(k: int, i: int) -> str:
    """Mountain/valley of the straight radial spoke between ring k-1's
    corner i and ring k's corner i. Alternates by corner index i around the
    ring, with the base flipping every ring (since ring_gender alternates
    by k) — so spoke_gender(k, i) and spoke_gender(k+1, i) are always
    opposite of each other for every i."""
    base = _opposite(ring_gender(k))
    return base if i % 2 == 0 else _opposite(base)


def cross_gender(i: int) -> str:
    """Mountain/valley of the crossed spoke (a ring panel's own diagonal),
    indexed by the corner it touches. Deliberately independent of k: at
    interior ring corner i, the four spoke-type creases are
    {spoke_gender(k,i), cross_gender(i+1), spoke_gender(k+1,i),
    cross_gender(i)}. Because spoke_gender(k,i) and spoke_gender(k+1,i) are
    always opposite (see spoke_gender), and cross_gender(i) is independent
    of k while cross_gender(i+1) is the opposite of cross_gender(i) (it
    alternates with i, same as spoke_gender's own i-alternation) — the four
    creases are provably two matched opposite pairs, i.e. exactly 2
    mountain + 2 valley, for every interior ring corner and every k. At the
    hub (k=0, no inward spokes), the two creases touching hub corner i are
    the straight spoke of panel i (spoke_gender(1,i)) and the crossed spoke
    of panel i+1 (cross_gender(i)) — an independent pair, not required to
    balance against anything else, so any fixed assignment works there;
    what matters is that together with the 2 boundary mountains they total
    an even degree (4), which they do by construction (2 boundary + 2
    spoke-type, always 4 total)."""
    return "mountain" if i % 2 == 0 else "valley"


@dataclass(frozen=True)
class FlasherParams:
    grid_divisions: int  # N; sheet is conceptually N×N grid units, N odd
    layer_gap_ratio: float  # unused (kept for API compatibility)
    height_ratio: float  # unused (kept for API compatibility)

    @property
    def rings(self) -> int:
        return (self.grid_divisions - 1) // 2


@dataclass
class Vertex:
    id: int
    position: tuple[float, float]


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
    ring_index: int  # 0 = hub, k = the panel ring between ring k-1 and ring k


@dataclass
class CreasePattern:
    vertices: list[Vertex]
    edges: list[Edge]
    faces: list[Face]
    adjacency: list[dict] = field(default_factory=list)
    ring_count: int = 0
    sides: int = 4


def _signed_area(pts: list[tuple[float, float]]) -> float:
    total = 0.0
    for a, b in zip(pts, pts[1:] + pts[:1]):
        total += a[0] * b[1] - b[0] * a[1]
    return 0.5 * total


def generate_flasher(params: FlasherParams) -> CreasePattern:
    n = params.grid_divisions
    if n % 2 != 1:
        raise ValueError(
            "grid_divisions must be odd, so the sheet has a single, well-centered "
            "hub cell (an even count splits the center between four cells)"
        )
    m = params.rings
    if m < 1:
        raise ValueError("grid_divisions must be >= 3 (at least one ring)")

    sides = SIDES
    half_angle = math.pi / sides
    phi = TWIST_RATIO * half_angle
    w = PLEAT_WIDTH

    def radius(k: int) -> float:
        apothem = HUB_APOTHEM + k * w
        return apothem / math.cos(half_angle)

    def corner(k: int, i: int) -> tuple[float, float]:
        r = radius(k)
        theta = 2.0 * math.pi * i / sides + k * phi
        return (r * math.cos(theta), r * math.sin(theta))

    def vid(k: int, i: int) -> int:
        return k * sides + (i % sides)

    vertices: list[Vertex] = []
    for k in range(m + 1):
        for i in range(sides):
            vertices.append(Vertex(id=vid(k, i), position=corner(k, i)))
    positions = {v.id: v.position for v in vertices}

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

    def circumferential_assignment(k: int) -> str:
        if k == m:
            return "border"
        return ring_gender(k)

    faces: list[Face] = []

    def make_face(vertex_ids: list[int], edge_assignments: list[str], ring_index: int) -> None:
        pts = [positions[v] for v in vertex_ids]
        if _signed_area(pts) < 0:
            length = len(vertex_ids)
            vertex_ids = vertex_ids[::-1]
            edge_assignments = [edge_assignments[(length - 2 - j) % length] for j in range(length)]
        edge_ids = [
            get_or_create_edge(vertex_ids[j], vertex_ids[(j + 1) % len(vertex_ids)], edge_assignments[j])
            for j in range(len(vertex_ids))
        ]
        faces.append(Face(id=len(faces), vertex_ids=vertex_ids, edge_ids=edge_ids, ring_index=ring_index))

    # Hub: a single rigid square — the fixed pivot everything else rotates
    # relative to.
    hub_ids = [vid(0, i) for i in range(sides)]
    hub_edge_assignments = [circumferential_assignment(0) for _ in range(sides)]
    make_face(hub_ids, hub_edge_assignments, ring_index=0)

    # Ring panels k=1..m. Panel i spans corner i to i+1; its own diagonal
    # (inner_b=vid(k-1,i+1) to outer_a=vid(k,i)) is the CROSSED spoke
    # cross_gender(i+1) — a real crease, not a facet triangulation seam —
    # which is what gives every interior corner its required even degree.
    for k in range(1, m + 1):
        for i in range(sides):
            inner_a, inner_b = vid(k - 1, i), vid(k - 1, i + 1)
            outer_a, outer_b = vid(k, i), vid(k, i + 1)
            circ_in = circumferential_assignment(k - 1)
            circ_out = circumferential_assignment(k)
            spoke_a = spoke_gender(k, i)  # inner_a - outer_a (shared with panel i-1)
            spoke_b = spoke_gender(k, i + 1)  # inner_b - outer_b (shared with panel i+1)
            diag = cross_gender(i + 1)  # inner_b - outer_a (this panel's own diagonal)

            make_face([inner_a, inner_b, outer_a], [circ_in, diag, spoke_a], ring_index=k)
            make_face([inner_b, outer_b, outer_a], [spoke_b, circ_out, diag], ring_index=k)

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
        sides=sides,
    )
