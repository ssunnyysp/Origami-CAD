# Origami CAD

A parametric viewer/simulator for origami "flasher" patterns — deployable twist-fold
wraps that collapse a flat square sheet into a compact form around its central hub cell.
A Python (FastAPI) backend owns all the geometry and fold math; a Node (Vite + React +
Three.js) frontend only renders.

## What it does

- Generates the **wrap-pinwheel flasher** crease pattern parametrically: a square sheet
  on an N×N grid (N odd, for a single well-centered hub cell), quartered into four
  congruent rectangular regions arranged in a C4 pinwheel around the hub. This is a
  hand-authored design (transcribed from a real paper model), not a procedural guess —
  see `backend/app/flasher/generator.py`'s module docstring for the full spec.
- Animates fold/unfold live via a "foldness" slider (0 = flat, 1 = folded)
- Draws a CAD-style crease overlay — mountain folds yellow, valley folds red, border
  dark — fading out as the model folds
- Renders two-sided paper: the top face takes the chosen color, the underside stays
  plain — like real origami paper
- Ships with 4 curated presets (7×7, 15×15, 23×23, 31×31 "Big Bang")

## Project layout

- `backend/app/flasher/generator.py` — crease-pattern generation (pure geometry, no physics)
- `backend/app/flasher/solver.py` — the fold simulation described above
- `backend/app/fold/` — FOLD file format import/export (see below)
- `backend/app/schemas.py` — the API contract (mirrored by hand in `frontend/src/model/types.ts`)
- `backend/app/presets.py` — curated flasher presets
- `frontend/src/api/` — typed API client and the geometry-fetching hooks
- `frontend/src/model/` — shared API types and the frame-interpolation helper
- `frontend/src/components/scene/` — the `@react-three/fiber` scene and mesh/crease rendering
- `frontend/src/components/pattern/` — flat 2-D crease-pattern view, an alternative to the 3-D scene
- `frontend/src/components/ui/` — control panel widgets (model selector, sliders, color picker, FOLD import/export)
- `frontend/src/store/` — zustand store holding presets, active params, view settings, theme, and imported-file state

## FOLD file support

Import and export of the [FOLD format](https://github.com/edemaine/fold) (the JSON-based
interchange format used by Origami Simulator, Rabbit Ear, and academic rigid-origami tools):

- **Import**: drag a `.fold` file onto the control panel (or click to browse). Multi-frame
  files (e.g. a flat crease pattern plus one or more folded states) show a frame picker.
  A flat crease-pattern frame is animated with a generic, best-effort fold solver (not the
  flasher-specific solver above, since an arbitrary imported pattern has no known hub); an
  already-folded 3-D frame is shown as a static pose rather than an invented animation.
  Malformed files fail with a specific error message instead of crashing.
- **Export**: the "Export FOLD" button serializes whatever is currently on screen (generated
  or imported) into a `.fold` file — the flat pattern as frame 0, the current folded pose as
  an inheriting `file_frames` entry — and is round-trip compatible: re-importing frame 0
  reconstructs the same pattern.
- See `backend/app/fold/` for the parser/writer and `backend/scripts/validate_fold.py`
  for the round-trip + sample-file validation harness.

## Development

Backend (Python 3.12+):

```
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```

**The backend does not auto-reload.** Editing `generator.py`/`solver.py`/anything backend
and expecting the running server to pick it up will silently serve stale results instead —
kill and restart the process after every backend edit.

Frontend (in a second terminal):

```
cd frontend
npm install
npm run dev          # vite dev server on :5173, proxies /api to :8000
npm run build         # tsc -b && vite build
npm run lint          # oxlint
```

Open http://localhost:5173 once both are running.
