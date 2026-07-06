"""Origami CAD geometry service.

The backend owns all model math: presets, crease-pattern generation, and the
fold solve. Geometry is solved as one full 0→1 foldness sweep per request so
the client never needs a physics round trip during animation — it just
interpolates between the returned frames.
"""

from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .flasher.generator import generate_flasher
from .flasher.solver import solve_sweep
from .presets import PRESETS
from .schemas import CreasePatternOut, GeometryRequest, GeometryResponse

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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
