# Origami CAD

A showcase viewer for parametric origami "flasher" patterns — deployable, concentric-ring
twist-fold tessellations — built with React, Three.js (`@react-three/fiber`), and TypeScript.

## What it does

- Generates flasher crease patterns parametrically (central polygon + spiral arms over
  concentric rings, controlled by sides, rings, spiral angle, wrap angle, and ring spread)
- Animates stow/deploy live via a "foldness" slider (0 = flat/deployed, 1 = wrapped/stowed)
- Draws a CAD-style crease overlay (mountain red / valley blue / border dark), toggleable
- Lets you change paper color, roughness, and metalness
- Ships with 4 curated presets (square, hexagonal, triangular, octagonal flashers)

## How folding works

Every vertex interpolates in cylindrical coordinates between the flat pattern and a wrapped
target state where each successive ring winds `wrapAngle` further around the hub at a slightly
larger layer radius and height. Leaving the winding angle unwrapped makes outer rings sweep
through multiple turns, so the sheet visibly coils around the hub — the signature flasher stow
motion. This is a kinematic visualization, not an isometric simulation: see
`docs/FLASHER_NOTES.md` for the exact math, the approximations made, and the roadmap to a
physically faithful model.

## Project layout

- `src/model/` — crease pattern data types, the flasher generator, and the fold engine
- `src/components/scene/` — the `@react-three/fiber` scene and per-ring/per-face rendering
- `src/components/ui/` — control panel widgets (model selector, sliders, color picker)
- `src/components/debug/` — a throwaway 2D SVG crease-pattern viewer used to sanity-check the
  generator's output; not wired into the main app
- `src/store/` — zustand store holding the active model params and view settings

## Not yet built (future work)

See `docs/FLASHER_NOTES.md` for the full roadmap. Highlights:

- Exact zero-thickness flasher geometry (polygon-involute arms, pleated arms / Lang's height order)
- Import/export (the FOLD format, SVG cut/score files)
- A true per-hinge rigid-origami solver (currently a per-vertex cylindrical interpolation)

## Development

```
npm install
npm run dev
```
