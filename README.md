# Origami CAD

A showcase viewer for parametric origami "flasher" patterns — deployable, concentric-ring
twist-fold tessellations — built with React, Three.js (`@react-three/fiber`), and TypeScript.

## What it does

- Generates flasher crease patterns parametrically (central polygon + concentric pleat rings)
- Animates folding live via a "foldness" slider (0 = flat, 1 = fully folded)
- Lets you change paper color, roughness, metalness, ring count, twist angle, and ring spread
- Ships with 4 curated presets (square, hexagonal, triangular, octagonal flashers)

## How folding works

Each ring is animated as a single rigid body: at full fold it's rotated by `ring index * twist
angle` and lifted to its own height, and the foldness slider interpolates every ring's transform
between flat (identity) and that folded target via lerp/slerp. This guarantees an exact,
non-self-intersecting result at both ends of the slider; mid-fold, individual triangles aren't
perfectly rigid (a deliberate simplification — see `src/model/foldEngine.ts`).

## Project layout

- `src/model/` — crease pattern data types, the flasher generator, and the fold engine
- `src/components/scene/` — the `@react-three/fiber` scene and per-ring/per-face rendering
- `src/components/ui/` — control panel widgets (model selector, sliders, color picker)
- `src/components/debug/` — a throwaway 2D SVG crease-pattern viewer used to sanity-check the
  generator's output; not wired into the main app
- `src/store/` — zustand store holding the active model params and view settings

## Not yet built (future work)

- Freehand crease-pattern drawing/editing
- Import/export (e.g. the FOLD format)
- A true per-hinge rigid-origami numeric solver (currently approximated per-ring)

## Development

```
npm install
npm run dev
```
