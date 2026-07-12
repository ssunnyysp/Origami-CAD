"""Hexagon/octagon flasher crease-pattern generator — a true "twist fold":
a regular n-gon hub surrounded by m concentric rings, each ring rotated
("twisted") by a fixed angle relative to the ring inside it. This is the
standard construction behind real flashers (Shafer, Lang's "twist" family,
the Guest & Pellegrino wrapping-fold): a central polygon, plus rings of
congruent trapezoidal panels, plus radial "spoke" creases that let each ring
rotate relative to its neighbor.

## Geometry

n = `sides` (hub/ring side count, must be even — 6 or 8 for a hexagon or
octagon hub). m = `rings` (pleat ring count).

Ring k's n corners sit on a circle of radius R_k, at angles offset by a fixed
twist φ from ring (k-1)'s corners:

    C[k][i] = R_k * (cos(θ_i + k·φ), sin(θ_i + k·φ)),   θ_i = 2π·i/n

R_k grows linearly with the ring's *apothem* (so pleat rings have constant
radial width w = `pleat_ratio` · hub apothem): R_k = (a0 + k·w) / cos(π/n).

Every ring's corners are the SAME polygon, just scaled up and rotated by kφ —
so ring k is congruent to ring 0 (up to scale), and every one of its n
panels is congruent to the others by n-fold rotational symmetry. φ is the
"twisted at a consistent angle ring-to-ring" the whole model turns on: φ = 0
reproduces mirror-symmetric nested polygons (which can only dome, never
twist — no rotational handedness); any φ ≠ 0 makes the pattern chiral, which
is what lets every ring rotate the SAME way simultaneously when folded (the
actual flasher wrap motion).

## Panels

Between ring k-1 and ring k, side i is the quadrilateral

    C[k-1][i], C[k-1][i+1], C[k][i+1], C[k][i]

Its two "circumferential" sides (C[k-1][i]-C[k-1][i+1] and C[k][i]-C[k][i+1])
are congruent copies of the same polygon edge at different radii; its two
"spoke" sides (C[k-1][i]-C[k][i] and C[k-1][i+1]-C[k][i+1]) are the radial
creases that let ring k hinge relative to ring k-1. Because a quadrilateral
with skewed (non-parallel) legs isn't guaranteed planar once its 4 corners
move independently, each panel is split by its own short diagonal into 2
triangles for meshing/solving — this diagonal is a facet edge (never a real
crease, always flat), and it is entirely internal to one panel, so it never
rigidly welds one panel to its neighbor the way an earlier (discarded)
version of this generator did by threading facet edges *between* panels.

## Crease assignment

- Circumferential creases alternate mountain/valley ring-to-ring:
  `ring_gender(k)` — the hub's own boundary (k=0) is always "mountain"; the
  outermost ring boundary (k=m) has no panel beyond it, so it is the sheet's
  physical edge ("border"), not a fold.
- Spoke creases alternate mountain/valley AROUND each ring (by corner index
  i), so a single ring's n radial creases are not all the same sense —
  consistent with a real flasher CP, where consecutive spokes fold opposite
  ways to let the ring gather into a stack rather than cone outward.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

HUB_CENTER = (0.0, 0.0)
HUB_APOTHEM = 1.0  # fixed hub half-width (apothem); everything else scales off this


def ring_gender(k: int) -> str:
    """Mountain/valley of ring k's own circumferential boundary crease.
    k=0 is the hub's own boundary (always mountain — the wrap's first
    fold), alternating outward from there."""
    if k == 0:
        return "mountain"
    return "mountain" if k % 2 == 1 else "valley"


def _opposite(gender: str) -> str:
    return "valley" if gender == "mountain" else "mountain"


def spoke_gender(k: int, i: int) -> str:
    """Mountain/valley of the radial spoke crease between ring k-1's corner i
    and ring k's corner i. Alternates by corner index i around the ring (not
    just ring-to-ring like the circumferential creases) — every other spoke
    in a ring folds the opposite way, which is what lets the ring gather
    into a flat stack instead of coning outward when the circumferential
    creases pull it closed."""
    base = _opposite(ring_gender(k))
    return base if i % 2 == 0 else _opposite(base)


@dataclass(frozen=True)
class FlasherParams:
    sides: int  # n; hub/ring polygon side count, must be even (6 or 8)
    rings: int  # m; number of concentric pleat rings, >= 1
    pleat_ratio: float  # ring radial width, as a fraction of the hub apothem
    twist_ratio: float  # twist angle per ring, as a fraction of pi/sides (0,1)


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
    ring_index: int  # 0 = hub, k = the panel ring between ring k-1 and ring k


@dataclass
class CreasePattern:
    vertices: list[Vertex]
    edges: list[Edge]
    faces: list[Face]
    adjacency: list[dict] = field(default_factory=list)
    ring_count: int = 0
    sides: int = 6


def _signed_area(pts: list[tuple[float, float]]) -> float:
    total = 0.0
    for a, b in zip(pts, pts[1:] + pts[:1]):
        total += a[0] * b[1] - b[0] * a[1]
    return 0.5 * total


def generate_flasher(params: FlasherParams) -> CreasePattern:
    n = params.sides
    m = params.rings
    if n % 2 != 0 or n < 4:
        raise ValueError("sides must be even and >= 4 (a hexagon=6 or octagon=8 hub)")
    if m < 1:
        raise ValueError("rings must be >= 1")
    if not (0.0 < params.twist_ratio < 1.0):
        raise ValueError("twist_ratio must be in (0, 1) — 0 gives a non-chiral pattern")

    half_angle = math.pi / n
    phi = params.twist_ratio * half_angle  # twist per ring
    w = params.pleat_ratio * HUB_APOTHEM  # radial pleat width

    def radius(k: int) -> float:
        apothem = HUB_APOTHEM + k * w
        return apothem / math.cos(half_angle)

    def corner(k: int, i: int) -> tuple[float, float]:
        r = radius(k)
        theta = 2.0 * math.pi * i / n + k * phi
        return (r * math.cos(theta), r * math.sin(theta))

    def vid(k: int, i: int) -> int:
        return k * n + (i % n)

    # --- vertices ------------------------------------------------------
    vertices: list[Vertex] = []
    for k in range(m + 1):
        for i in range(n):
            vertices.append(Vertex(id=vid(k, i), position=corner(k, i)))
    positions = {v.id: v.position for v in vertices}

    # --- edges -----------------------------------------------------------
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

    # --- faces -------------------------------------------------------------
    faces: list[Face] = []

    def make_face(vertex_ids: list[int], edge_assignments: list[str], ring_index: int) -> None:
        pts = [positions[v] for v in vertex_ids]
        if _signed_area(pts) < 0:
            length = len(vertex_ids)
            # Reversed vertex list: rev[j] = orig[-1-j]. Edge j of the
            # reversed polygon runs rev[j]-rev[j+1] = orig[-1-j]-orig[-2-j],
            # i.e. the same *segment* as original edge index (length-2-j) —
            # re-derived directly rather than trusting a slice trick, since
            # an earlier version of this got the alignment wrong.
            vertex_ids = vertex_ids[::-1]
            edge_assignments = [edge_assignments[(length - 2 - j) % length] for j in range(length)]
        edge_ids = [
            get_or_create_edge(vertex_ids[j], vertex_ids[(j + 1) % len(vertex_ids)], edge_assignments[j])
            for j in range(len(vertex_ids))
        ]
        faces.append(Face(id=len(faces), vertex_ids=vertex_ids, edge_ids=edge_ids, ring_index=ring_index))

    # Hub: a single rigid regular n-gon.
    hub_ids = [vid(0, i) for i in range(n)]
    hub_edge_assignments = [circumferential_assignment(0) for _ in range(n)]
    make_face(hub_ids, hub_edge_assignments, ring_index=0)

    # Ring panels k=1..m, each split into 2 triangles by its shorter diagonal.
    for k in range(1, m + 1):
        for i in range(n):
            inner_a, inner_b = vid(k - 1, i), vid(k - 1, i + 1)
            outer_a, outer_b = vid(k, i), vid(k, i + 1)
            circ_in = circumferential_assignment(k - 1)
            circ_out = circumferential_assignment(k)
            spoke_a = spoke_gender(k, i)  # inner_a - outer_a
            spoke_b = spoke_gender(k, i + 1)  # inner_b - outer_b

            d1 = math.dist(positions[inner_a], positions[outer_b])  # inner_a-outer_b
            d2 = math.dist(positions[inner_b], positions[outer_a])  # inner_b-outer_a
            if d1 <= d2:
                # triangles (inner_a, inner_b, outer_b) and (inner_a, outer_b, outer_a)
                make_face(
                    [inner_a, inner_b, outer_b],
                    [circ_in, spoke_b, "facet"],
                    ring_index=k,
                )
                make_face(
                    [inner_a, outer_b, outer_a],
                    ["facet", circ_out, spoke_a],
                    ring_index=k,
                )
            else:
                # triangles (inner_a, inner_b, outer_a) and (inner_b, outer_b, outer_a)
                make_face(
                    [inner_a, inner_b, outer_a],
                    [circ_in, "facet", spoke_a],
                    ring_index=k,
                )
                make_face(
                    [inner_b, outer_b, outer_a],
                    [spoke_b, circ_out, "facet"],
                    ring_index=k,
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
        sides=n,
    )
