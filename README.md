# Origami CAD

A showcase viewer for parametric origami "flasher" patterns — deployable, concentric-ring
twist-fold tessellations. A Python (FastAPI) backend owns all the geometry math; a Node
(Vite + React + Three.js) frontend renders it.

## What it does

- Generates hexagon/octagon-hub twist-fold flasher crease patterns parametrically: a
  regular n-gon hub surrounded by concentric rings of trapezoidal panels, each ring
  twisted by a fixed angle relative to the ring inside it — the standard flasher
  construction (Shafer, Lang's "twist" family)
- Animates stow/deploy live via a "foldness" slider (0 = flat/deployed, 1 = wrapped/stowed)
- Draws a CAD-style crease overlay — mountain folds blue (paper folds up), valley folds red
  (paper folds down), border dark — fading out as the model folds
- Renders two-sided paper: the top face takes the chosen color, the underside stays plain —
  like real origami paper
- Ships with 4 curated presets (two hexagon, two octagon hubs at different ring counts)

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

The crease pattern is a true twist fold: a regular n-gon hub, surrounded by `rings`
concentric rings of trapezoidal panels. Ring k's corners are ring (k-1)'s corners scaled
outward and rotated by a fixed twist angle — any nonzero twist makes the pattern chiral
(not mirror-symmetric), which is what lets every ring rotate the same way simultaneously
when folded (the actual flasher wrap motion) instead of only doming. Circumferential
creases alternate mountain/valley ring-to-ring; radial "spoke" creases alternate
mountain/valley around each ring.

Folding is solved server-side in two stages: a closed-form rigid forward-kinematics pass
(walking the crease pattern's face-adjacency spanning tree from the pinned hub outward,
rotating each panel rigidly about its crease) predicts a qualitatively-correct pose from a
single shared fold-angle schedule, then a short, deterministic length-projection +
collision-repulsion pass (no random seed, no velocity/damping physics) corrects the
residual gap between that prediction and an exact rigid solve. See `solver.py`'s module
docstring for why an exact closed-form solve isn't implemented, and
`scripts/validate_flasher.py` for how fold quality (strain, self-intersection, monotonic
gathering) is measured. `docs/FLASHER_NOTES.md` describes the earlier polygonal model this
replaced.

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
