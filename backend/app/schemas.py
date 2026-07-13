"""API contract. Field names are camelCase to match the frontend's TypeScript
types — the JSON that leaves this server is the same shape the React app's
`CreasePattern` type already describes."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .flasher.generator import CreasePattern, FlasherParams


class GeometryRequest(BaseModel):
    """Square-flasher parameters as the UI holds them.

    Frozen so identical requests hash equal — the geometry endpoint caches on
    the whole request object."""

    model_config = {"frozen": True}

    gridDivisions: int = Field(ge=7, le=41)
    layerGapRatio: float = Field(default=0.08, gt=0, le=0.5)
    heightRatio: float = Field(default=0.25, ge=0, le=1)

    @field_validator("gridDivisions")
    @classmethod
    def _odd_grid(cls, v: int) -> int:
        if v % 2 != 1:
            raise ValueError(
                "gridDivisions must be odd, so the sheet has a single, well-centered hub cell"
            )
        return v

    def to_params(self) -> FlasherParams:
        return FlasherParams(
            grid_divisions=self.gridDivisions,
            layer_gap_ratio=self.layerGapRatio,
            height_ratio=self.heightRatio,
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


# --- FOLD import/export (see app/fold/) -------------------------------------


class FoldFrameInfo(BaseModel):
    """One selectable frame from an uploaded FOLD file (the file's frame 0
    plus each entry of file_frames), for the "pick which fold-state to load"
    UI."""

    index: int
    title: str | None = None
    classes: list[str] = []


class FoldImportRequest(BaseModel):
    document: dict
    frameIndex: int | None = None


class FoldImportResponse(BaseModel):
    pattern: CreasePatternOut
    foldnessSamples: list[float]
    frames: list[list[float]]
    availableFrames: list[FoldFrameInfo]
    selectedFrameIndex: int
    warnings: list[str]


class FoldExportRequest(BaseModel):
    pattern: CreasePatternOut
    # The currently-displayed folded frame, xyz triples indexed by vertex id
    # (i.e. exactly what interpolatePositions() produces client-side).
    positions: list[float]
    title: str = "Origami CAD export"
