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

## Architecture

```
frontend/   Vite + React + TypeScript + @react-three/fiber — rendering and UI only
backend/    FastAPI — presets, crease-pattern generation, and the fold solver
```

The fold solver is too expensive to run at animation rate in the browser, and the
client has zero fold logic. Instead the backend solves the **entire fold trajectory
once** per parameter set: `POST /api/flasher/geometry` returns the crease pattern plus
61 frames of vertex positions (foldness 0.00 → 1.00). The frontend linearly interpolates
between adjacent frames at render time, so dragging the slider or animating is pure
client-side lerp with zero network traffic per frame — a new request only fires when the
structural parameters (grid size, etc.) change, and `GeometryRequest` is `@lru_cache`d
server-side so re-selecting a previously-seen preset is free.

API:

- `GET /api/presets` — curated flasher presets
- `POST /api/flasher/geometry` — flasher params in, crease pattern + fold-sweep frames out
- `GET /api/health` — liveness check
- `POST /api/fold/import` — parse an uploaded `.fold` file (see FOLD file support below)
- `POST /api/fold/export` — serialize the current pattern + folded pose to `.fold`

## How folding works

The crease pattern (`generator.py`) is pure geometry with no notion of time or folding:
each of the four regions has a 45° diagonal running from the hub corner out toward the
sheet's corner, an accordion of horizontal/vertical **pleat** folds (mountain/valley
alternating outward from the hub) filling the hub-side of that diagonal, and an
uncreased flap on the outer side that wraps around the hub as the accordion compresses.
The hub cell's four boundary edges fold ~90° as wall bends.

The solver (`solver.py`) is a forward position-based-dynamics simulation — the same
family of approach as origamisimulator.org — driven from the flat sheet, not a rigid
target composed and interpolated toward. Each frame ramps every crease's target angle a
little further and settles the sheet with a few constraint-projection passes (edge
length, self-collision, then dihedral angle). Two things about *how* the dihedral
targets are weighted are what make the fold actually land on the crease pattern instead
of crumpling:

1. **The pleats (and hub-wall bends) lead; the diagonal is only a passive aid.** The
   diagonal is not meant to be a hard-driven fold — if it's weighted as strongly as the
   pleats it fights them and the region crumples instead of forming its wave. So the
   diagonal is driven at low weight (`DIAGONAL_WEIGHT`): it folds only as much as the
   surrounding pleats leave room for.
2. **Facets (the triangulation diagonals inside each cell) are held close to flat**
   (`FACET_WEIGHT`), so cells stay rigid panels and the bending happens sharply *on* the
   crease lines rather than smeared across a wavy surface.

**The flasher stows flat** — it compresses radially into a low disc sitting just under
the hub plane, the way the paper model does, rather than growing into a tower, tilting,
or dishing in the middle. That is the binding constraint on the solver's tuning, and it
is checked three ways: stowed height, tilt of the best-fit plane (0.0° on every preset),
and the radial height profile from hub to rim.

Within that limit, the sheet must **wrap rotationally** — every ring turning about the
hub, progressively more further out, so it winds up clockwise/counter-clockwise like the
paper model. That is not automatic: the sheet can also just crush straight inward, which
buckles the rings and reads as crumpling, and the two are near-equally valid solutions to
the same constraints. The solver breaks that tie with a small coherent swirl applied as
the fold progresses (`SEED_SWIRL`), and caps how hard the creases are driven (`CAP`),
since past a certain point the innermost ring starts turning against the wrap. Notably the
swirl *lowers* edge strain, confirming the spiral is the natural mode rather than an
imposed one — and a stronger swirl stabilises it enough to allow a deeper fold. How hard
each preset is driven, how much it is settled, and how much it is swirled are set together
per grid size by a small table (`FOLD_PROFILE`), because each size runs into a different
limit first: the smallest into facet flex, the middle into stow height, the largest into
strain and dishing.

Self-collision is **vertex-versus-triangle**, not vertex-versus-vertex. A vertex-pair test
can only stop layers passing through each other by holding them far apart, which inflates
the stow, and it structurally cannot catch the crossing that actually happens here — an
edge slicing through the middle of a facet with no two vertices ever close. A real
point-to-triangle test prevents penetration directly, so layers stay thin and the stow
stays flat. Bigger sheets also get more settling passes, since the fold propagates outward
from the pinned hub one ring at a time.

Every preset measures zero true self-intersection across the whole sweep, 98–100%
mountain/valley sign fidelity, a coherent spiral (rotation growing outward, ~61–77° at
the rim), and a stow height of 1.1–1.8 units against a flat-sheet cell size of 1.0. Edge
strain runs ~7–9%: the pattern is not perfectly rigidly foldable (a 45° diagonal can't
span a non-square region corner-to-corner — see the generator's docstring), so some of
that incompatibility has to go somewhere. See `solver.py`'s module docstring for the full
reasoning and measured numbers.

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

## Known limitations

- The pattern does not rigidly close to an exact box (see "How folding works" above) —
  this is a geometric property of the current pattern, verified directly, not a bug.
- Larger presets take longer to solve: roughly 2s / 20s / 55s / 81s for 7×7 / 15×15 / 23×23
  / 31×31 — the deep fold needs many settling passes. The result is cached per parameter set, so this cost is paid once per preset
  rather than per frame, and the UI shows a "Solving fold…" state meanwhile.
- `backend/app/flasher/fold_engine.py` is unused dead code left over from an earlier
  kinematic-wrap approach that the current solver replaced — not imported anywhere.

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

Open http://localhost:5173 once both are running. `.claude/launch.json` defines the same
two processes for the IDE launcher. There is no test suite in this repo.
