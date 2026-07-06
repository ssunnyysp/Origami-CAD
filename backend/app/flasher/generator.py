"""Parametric flasher crease-pattern generator.

Port of the original frontend flasherGenerator.ts — the data model is custom
(not the FOLD format) because patterns are generated parametrically rather
than imported from authored files.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FlasherParams:
    sides: int  # n, sides of the central polygon / rotational symmetry order
    rings: int  # k, concentric pleat rings around the central polygon
    spiral_angle: float  # radians; per-ring angular offset in the FLAT pattern
    wrap_angle: float  # radians; per-ring extra wrap around the hub when FOLDED
    radius_ratio: float  # > 1, each ring's outer radius = inner radius * radius_ratio
    central_radius: float  # r0, circumradius of the central polygon


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
    vertex_ids: list[int]  # ordered, CCW in the flat pattern
    edge_ids: list[int]  # edges bounding this face, same winding order
    ring_index: int  # 0 = central polygon


@dataclass
class CreasePattern:
    vertices: list[Vertex]
    edges: list[Edge]
    faces: list[Face]
    adjacency: list[dict] = field(default_factory=list)
    ring_count: int = 0
    sides: int = 0


def flasher_vertex_id(sides: int, ring: int, sector: int) -> int:
    """Vertex ids encode (ring, sector) so consumers can recover both."""
    return ring * sides + sector % sides


def generate_flasher(params: FlasherParams) -> CreasePattern:
    n = params.sides
    rings = params.rings

    # Ring radii: R[0] = central_radius, R[j] = R[j-1] * radius_ratio.
    radii = [params.central_radius]
    for _ in range(rings):
        radii.append(radii[-1] * params.radius_ratio)

    # Each ring is rotated by j * spiral_angle relative to the hub, so the
    # "spoke" edges connecting ring j-1 to ring j slant tangentially and chain
    # into n discrete spiral arms — the defining feature of a flasher flat
    # pattern (cf. Guest & Pellegrino's membrane wrap, Lang's flasher).
    vertices: list[Vertex] = []
    for j in range(rings + 1):
        for i in range(n):
            angle = 2 * math.pi * i / n + j * params.spiral_angle
            vertices.append(
                Vertex(
                    id=flasher_vertex_id(n, j, i),
                    position=(radii[j] * math.cos(angle), radii[j] * math.sin(angle)),
                )
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

    # Central polygon face (ring 0). Its boundary is where the wrap begins —
    # mountain, so the arms fold up and around the hub.
    hub_vertex_ids = [flasher_vertex_id(n, 0, i) for i in range(n)]
    hub_edge_ids = [
        get_or_create_edge(flasher_vertex_id(n, 0, i), flasher_vertex_id(n, 0, i + 1), "mountain")
        for i in range(n)
    ]
    faces.append(Face(id=0, vertex_ids=hub_vertex_ids, edge_ids=hub_edge_ids, ring_index=0))

    # Concentric pleat rings, each split into n quad sectors, each sector split
    # into 2 triangles: T1 = (A0, A1, B0), T2 = (A1, B0, B1).
    #
    # Crease labeling follows the wrap geometry rather than a flat-foldability
    # proof: the spiral spokes (A0→B0) are the primary wrap creases (mountain),
    # the sector diagonals (A1→B0) take the counter-fold (valley), and the
    # interior ring boundaries bend only gently in the wrapped state (facet).
    for j in range(1, rings + 1):
        inner_assignment = "mountain" if j == 1 else "facet"
        outer_assignment = "border" if j == rings else "facet"

        for i in range(n):
            a0 = flasher_vertex_id(n, j - 1, i)
            a1 = flasher_vertex_id(n, j - 1, i + 1)
            b0 = flasher_vertex_id(n, j, i)
            b1 = flasher_vertex_id(n, j, i + 1)

            e_a0a1 = get_or_create_edge(a0, a1, inner_assignment)
            e_b0b1 = get_or_create_edge(b0, b1, outer_assignment)
            e_a0b0 = get_or_create_edge(a0, b0, "mountain")
            e_a1b1 = get_or_create_edge(a1, b1, "mountain")
            e_diagonal = get_or_create_edge(a1, b0, "valley")

            faces.append(
                Face(
                    id=len(faces),
                    vertex_ids=[a0, a1, b0],
                    edge_ids=[e_a0a1, e_diagonal, e_a0b0],
                    ring_index=j,
                )
            )
            faces.append(
                Face(
                    id=len(faces),
                    vertex_ids=[a1, b0, b1],
                    edge_ids=[e_diagonal, e_b0b1, e_a1b1],
                    ring_index=j,
                )
            )

    # Face adjacency: any two faces sharing an edge id are neighbors. Kept in
    # the payload so a future per-hinge rigid solver can reuse it without
    # changing the API contract.
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
        ring_count=rings,
        sides=n,
    )
