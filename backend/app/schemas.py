"""API contract. Field names are camelCase to match the frontend's TypeScript
types — the JSON that leaves this server is the same shape the React app's
`CreasePattern` type already describes."""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from .flasher.generator import CreasePattern, FlasherParams

DEG = math.pi / 180


class GeometryRequest(BaseModel):
    """Flasher parameters as the UI holds them (angles in degrees).

    Frozen so identical requests hash equal — the geometry endpoint caches on
    the whole request object."""

    model_config = {"frozen": True}

    sides: int = Field(ge=3, le=16)
    rings: int = Field(ge=1, le=24)
    spiralAngleDeg: float = Field(ge=0, le=60)
    wrapAngleDeg: float = Field(ge=0, le=180)
    radiusRatio: float = Field(gt=1, le=2)
    centralRadius: float = Field(gt=0, le=10)

    def to_params(self) -> FlasherParams:
        return FlasherParams(
            sides=self.sides,
            rings=self.rings,
            spiral_angle=self.spiralAngleDeg * DEG,
            wrap_angle=self.wrapAngleDeg * DEG,
            radius_ratio=self.radiusRatio,
            central_radius=self.centralRadius,
        )


class VertexOut(BaseModel):
    id: int
    position: dict[str, float]  # {x, y}


class EdgeOut(BaseModel):
    id: int
    v0: int
    v1: int
    assignment: str


class FaceOut(BaseModel):
    id: int
    vertexIds: list[int]
    edgeIds: list[int]
    ringIndex: int


class CreasePatternOut(BaseModel):
    vertices: list[VertexOut]
    edges: list[EdgeOut]
    faces: list[FaceOut]
    adjacency: list[dict]
    ringCount: int
    sides: int

    @classmethod
    def from_pattern(cls, pattern: CreasePattern) -> "CreasePatternOut":
        return cls(
            vertices=[
                VertexOut(id=v.id, position={"x": v.position[0], "y": v.position[1]})
                for v in pattern.vertices
            ],
            edges=[
                EdgeOut(id=e.id, v0=e.v0, v1=e.v1, assignment=e.assignment)
                for e in pattern.edges
            ],
            faces=[
                FaceOut(id=f.id, vertexIds=f.vertex_ids, edgeIds=f.edge_ids, ringIndex=f.ring_index)
                for f in pattern.faces
            ],
            adjacency=pattern.adjacency,
            ringCount=pattern.ring_count,
            sides=pattern.sides,
        )


class GeometryResponse(BaseModel):
    pattern: CreasePatternOut
    # frames[k] holds xyz triples (indexed by vertex id) at foldnessSamples[k];
    # the client lerps between adjacent frames for arbitrary foldness values.
    foldnessSamples: list[float]
    frames: list[list[float]]
