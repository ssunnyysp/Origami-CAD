import { Canvas } from "@react-three/fiber";
import { Grid, OrbitControls } from "@react-three/drei";
import { DoubleSide } from "three";
import type { FlasherGeometry } from "../../model/types";
import type { Theme } from "../../store/useAppStore";
import { FlasherModel } from "./FlasherModel";
import { FoldAnimator } from "./FoldAnimator";

interface Props {
  geometry: FlasherGeometry | null;
  foldness: number;
  color: string;
  roughness: number;
  metalness: number;
  theme: Theme;
}

// Matches index.css's --stage / --stage-line / --accent per theme. Kept as
// plain JS constants (not read from CSS variables) since Three.js color
// props need literal values, not custom-property references.
//
// In dark mode the background is deliberately much lighter than the rest
// of the UI chrome (see --stage in index.css) — a mid-grey "photography
// studio" backdrop, the way product shots are actually lit, so the folded
// paper reads as a well-lit subject instead of receding into a dark void.
const SCENE_COLORS: Record<
  Theme,
  { background: string; hemiSky: string; hemiGround: string; cell: string; section: string }
> = {
  light: {
    background: "#eef0f4",
    hemiSky: "#ffffff",
    hemiGround: "#c7cdd8",
    cell: "#aab1bd",
    section: "#2563eb",
  },
  dark: {
    background: "#55534f",
    hemiSky: "#e8e4dc",
    hemiGround: "#3a3835",
    cell: "#454340",
    section: "#3b82f6",
  },
};

// 16 units across regardless of the pattern's own coordinate scale — matches
// whatever the flat generated flasher used to normalize to (gridDivisions
// units across), generalized so an imported FOLD file (arbitrary units) gets
// the same treatment.
function modelScale(geometry: FlasherGeometry | null): number {
  let maxAbs = 0;
  for (const v of geometry?.pattern.vertices ?? []) {
    maxAbs = Math.max(maxAbs, Math.abs(v.position.x), Math.abs(v.position.y));
  }
  return maxAbs > 0 ? 16 / (2 * maxAbs) : 1;
}

export function Scene({ geometry, foldness, color, roughness, metalness, theme }: Props) {
  // Never remount the Canvas — it blanks the view while the WebGL context and
  // scene rebuild. Instead of moving the camera per preset, the model group
  // is scale-normalized to a 16-unit sheet and the camera stays fixed.
  const cameraDistance = 34;
  const sceneColors = SCENE_COLORS[theme];

  return (
    // Camera via the Canvas prop (not drei's <PerspectiveCamera makeDefault>):
    // OrbitControls orients the built-in camera toward its target on mount,
    // deterministically — the makeDefault handoff races with controls on
    // first mount and can leave the camera staring into empty space.
    <Canvas
      camera={{ position: [0, -cameraDistance * 0.7, cameraDistance * 0.7], fov: 45 }}
      onCreated={({ camera }) => camera.lookAt(0, 0, 0)}
    >
      {/* Matches the page's background (see index.css --bg per theme). */}
      <color attach="background" args={[sceneColors.background]} />
      {/* Static model — the user orbits manually; no auto-rotation. */}
      <OrbitControls />
      {/* Local lights only — a CDN-fetched Environment map suspends the whole
          scene (blank canvas) whenever the network is slow or offline. The
          hemisphere's ground tone flips dark/light with the theme so the
          model doesn't look like it's floating in a mismatched void, but its
          sky tone and the directional lights stay bright either way — the
          paper itself should always read as well-lit paper, not go muddy
          just because the surrounding chrome went dark. */}
      <hemisphereLight args={[sceneColors.hemiSky, sceneColors.hemiGround, 0.8]} />
      <directionalLight position={[5, -6, 8]} intensity={1.5} />
      <directionalLight position={[-6, 4, 3]} intensity={0.5} />
      <ambientLight intensity={0.4} />
      {/* Baseline reference grid, sitting exactly in the flat sheet's own
          resting plane (z = 0, the plane the pinned hub never leaves — see
          solver.py). Left unscaled and unrotated (a THREE.PlaneGeometry lies
          in the XY plane by default) so it reads as a fixed drafting-table
          surface: its cell size never changes across presets or imports,
          only the model's apparent size relative to it does — a stable
          ruler for "how big is this pattern," not just decoration. */}
      <Grid
        args={[80, 80]}
        cellSize={2}
        cellThickness={0.9}
        cellColor={sceneColors.cell}
        sectionSize={10}
        sectionThickness={1.3}
        sectionColor={sceneColors.section}
        fadeDistance={48}
        fadeStrength={1}
        infiniteGrid
        // drei defaults to BackSide, visible only from -Z; the camera orbits
        // around the +Z side (see the pinned hub's z=0 plane above) and the
        // user can orbit underneath too, so both sides need to render.
        side={DoubleSide}
      />
      <FoldAnimator />
      <group scale={modelScale(geometry)}>
        <FlasherModel
          geometry={geometry}
          foldness={foldness}
          color={color}
          roughness={roughness}
          metalness={metalness}
          theme={theme}
        />
      </group>
    </Canvas>
  );
}
