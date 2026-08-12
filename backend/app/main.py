"""Origami CAD geometry service.

The backend owns all model math: presets, crease-pattern generation, and the
fold solve. Geometry is solved as one full 0→1 foldness sweep per request so
the client never needs a physics round trip during animation — it just
interpolates between the returned frames.
"""

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .flasher.anatomy import classify_cells
from .flasher.generator import FlasherParams, generate_flasher
from .flasher.solver import solve_sweep
from .fold.errors import FoldValidationError
from .fold.exporter import build_fold_document
from .fold.importer import import_fold_document
from .presets import PRESETS
from .schemas import (
    CellAnatomyOut,
    CreasePatternOut,
    FoldExportRequest,
    FoldFrameInfo,
    FoldImportRequest,
    FoldImportResponse,
    GeometryRequest,
    GeometryResponse,
    PatternAnatomyResponse,
)

app = FastAPI(title="Origami CAD API")

# The Vite dev server proxies /api here, so same-origin requests need no CORS;
# this covers direct access (e.g. the frontend served from another host).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/presets")
def get_presets() -> list[dict]:
    return PRESETS


@lru_cache(maxsize=32)
def _solve_geometry(request: GeometryRequest) -> GeometryResponse:
    params = request.to_params()
    pattern = generate_flasher(params)
    samples, frames = solve_sweep(pattern, params)
    return GeometryResponse(
        pattern=CreasePatternOut.from_pattern(pattern),
        foldnessSamples=samples,
        frames=frames,
    )


@app.post("/api/flasher/geometry")
def get_geometry(request: GeometryRequest) -> GeometryResponse:
    # GeometryRequest is a frozen-shaped value object, so identical parameter
    # sets (e.g. re-selecting a preset) are served from cache.
    return _solve_geometry(request)


@lru_cache(maxsize=32)
def _classify_pattern(grid_divisions: int) -> PatternAnatomyResponse:
    # layer_gap_ratio/height_ratio don't affect generate_flasher (pure crease
    # geometry, no physics) — see the FlasherParams docstring — so any value
    # is fine here.
    pattern = generate_flasher(FlasherParams(grid_divisions=grid_divisions, layer_gap_ratio=0.1, height_ratio=0.9))
    cells = classify_cells(pattern, grid_divisions)
    h = (grid_divisions - 1) // 2
    return PatternAnatomyResponse(
        n=grid_divisions, h=h, cells=[CellAnatomyOut.from_cell(c) for c in cells]
    )


@app.get("/api/flasher/anatomy")
def get_pattern_anatomy(gridDivisions: int) -> PatternAnatomyResponse:
    """Cell-by-cell crease classification for the crease-pattern-anatomy
    reference view — derived straight from generate_flasher's own output, so
    it can never drift from the actual crease pattern (see app/flasher/anatomy.py)."""
    if gridDivisions % 2 != 1:
        raise HTTPException(status_code=422, detail="gridDivisions must be odd")
    if not (7 <= gridDivisions <= 41):
        raise HTTPException(status_code=422, detail="gridDivisions must be between 7 and 41")
    return _classify_pattern(gridDivisions)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/fold/import")
def import_fold(request: FoldImportRequest) -> FoldImportResponse:
    """Parse an uploaded .fold file into the app's crease-pattern model. Any
    problem with the file (missing/malformed fields, out-of-range indices,
    bad frameIndex) comes back as a 422 with a human-readable message rather
    than a 500 — see app/fold/importer.py for the validation this wraps."""
    try:
        result = import_fold_document(request.document, request.frameIndex)
    except FoldValidationError as err:
        raise HTTPException(status_code=422, detail=str(err))
    except Exception as err:  # last-resort guard: never let a malformed file 500
        raise HTTPException(status_code=422, detail=f"could not parse FOLD file: {err}")

    return FoldImportResponse(
        pattern=CreasePatternOut.from_pattern(result.pattern),
        foldnessSamples=result.foldness_samples,
        frames=result.frames,
        availableFrames=[FoldFrameInfo(**f) for f in result.available_frames],
        selectedFrameIndex=result.selected_frame_index,
        warnings=result.warnings,
    )


@app.post("/api/fold/export")
def export_fold(request: FoldExportRequest) -> dict:
    """Serialize the currently-displayed pattern + folded frame (whatever the
    client has on screen, generated or imported) into FOLD JSON."""
    try:
        return build_fold_document(request.pattern, request.positions, request.title)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
