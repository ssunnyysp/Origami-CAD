# Origami CAD

A showcase viewer for parametric origami "flasher" patterns — deployable, concentric-ring
twist-fold tessellations. A Python (FastAPI) backend owns all the geometry math; a Node
(Vite + React + Three.js) frontend renders it.

## What it does

- Generates square-flasher crease patterns parametrically: a SQUARE sheet on an N×N grid
  around a central hub, in the style of Jeremy Shafer's flashers (Big Bang = 32×32)
- Animates stow/deploy live via a "foldness" slider (0 = flat/deployed, 1 = wrapped/stowed)
- Draws a CAD-style crease overlay — mountain folds blue (paper folds up), valley folds red
  (paper folds down), border dark — fading out as the model folds
- Renders two-sided paper: the top face takes the chosen color, the underside stays plain —
  like real origami paper
- Ships with 4 curated presets; the default Simple Flasher (8×8) folds from a flat square
  into a cube-proportioned block, and the app opens on the folded form so dragging the
  slider unfolds it

## Architecture

```
frontend/   Vite + React + TypeScript + @react-three/fiber — rendering and UI only
backend/    FastAPI — presets, crease-pattern generation, and the fold solver
```

The fold solver runs at animation rate on screen, so it can't sit behind a per-frame HTTP
call. Instead the backend solves the **entire fold trajectory once** per parameter set:
`POST /api/flasher/geometry` returns the crease pattern plus vertex positions at 51 foldness
samples (0.00 → 1.00 in 0.02 steps, the solver's native substep). The frontend linearly
interpolates between adjacent frames at render time, so dragging the slider and the fold
animation stay at 60fps with zero network traffic.

API:

- `GET /api/presets` — curated flasher presets
- `POST /api/flasher/geometry` — flasher params in, crease pattern + fold-sweep frames out
- `GET /api/health` — liveness check

## How folding works

The crease pattern is the classic flasher structure: the sheet's two main diagonals split it
into 4 triangular quadrants; in each quadrant the grid lines parallel to the near edge are the
pleats, alternating mountain/valley; crossing a diagonal flips every pleat's gender (Shafer:
"every crease should get mountained and valleyed"), which is what turns the collapse into a
spiral wrap instead of a flat twist fold. Cells along the diagonals carry X creases — the
reverse folds that turn a pleat 90° around the hub corner.

To fold, every vertex is attracted toward a kinematic target in "square-polar" coordinates
(taxicab radius + perimeter position) wrapping around the hub column, while a position-based
dynamics pass enforces that every mesh edge keeps its flat-pattern length — paper folds, it
doesn't stretch — so the sheet collapses into the compact wrapped square by pleating at the
creases. `docs/FLASHER_NOTES.md` describes the earlier polygonal model this replaced.

## Project layout

- `backend/app/flasher/` — crease-pattern generator, kinematic fold engine, PBD fold solver
- `backend/app/schemas.py` — the API contract (mirrored by `frontend/src/model/types.ts`)
- `backend/app/presets.py` — curated flasher presets
- `frontend/src/api/` — typed API client and the geometry-fetching hook
- `frontend/src/model/` — shared API types and the frame-interpolation helper
- `frontend/src/components/scene/` — the `@react-three/fiber` scene and mesh/crease rendering
- `frontend/src/components/ui/` — control panel widgets (model selector, sliders, color picker)
- `frontend/src/store/` — zustand store holding presets, active params, and view settings

## Not yet built (future work)

See `docs/FLASHER_NOTES.md` for the full roadmap. Highlights:

- Exact zero-thickness flasher geometry (polygon-involute arms, pleated arms / Lang's height order)
- Import/export (the FOLD format, SVG cut/score files)
- A true per-hinge rigid-origami solver (currently kinematic target + edge-length projection)

## Development

Backend (Python 3.12+):

```
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000 --reload
```

Frontend (in a second terminal):

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies `/api` to the backend on port 8000.
