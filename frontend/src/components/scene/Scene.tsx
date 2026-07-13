import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { FlasherGeometry } from "../../model/types";
import { FlasherModel } from "./FlasherModel";
import { FoldAnimator } from "./FoldAnimator";

interface Props {
  geometry: FlasherGeometry | null;
  foldness: number;
  color: string;
  roughness: number;
  metalness: number;
}

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

export function Scene({ geometry, foldness, color, roughness, metalness }: Props) {
  // Never remount the Canvas — it blanks the view while the WebGL context and
  // scene rebuild. Instead of moving the camera per preset, the model group
  // is scale-normalized to a 16-unit sheet and the camera stays fixed.
  const cameraDistance = 34;

  return (
    // Camera via the Canvas prop (not drei's <PerspectiveCamera makeDefault>):
    // OrbitControls orients the built-in camera toward its target on mount,
    // deterministically — the makeDefault handoff races with controls on
    // first mount and can leave the camera staring into empty space.
    <Canvas
      camera={{ position: [0, -cameraDistance * 0.7, cameraDistance * 0.7], fov: 45 }}
      onCreated={({ camera }) => camera.lookAt(0, 0, 0)}
    >
      {/* Matches the page's warm paper background (see index.css --paper). */}
      <color attach="background" args={["#eceadf"]} />
      {/* Static model — the user orbits manually; no auto-rotation. */}
      <OrbitControls />
      {/* Local lights only — a CDN-fetched Environment map suspends the whole
          scene (blank canvas) whenever the network is slow or offline. */}
      <hemisphereLight args={["#ffffff", "#d8d2c4", 0.8]} />
      <directionalLight position={[5, -6, 8]} intensity={1.5} />
      <directionalLight position={[-6, 4, 3]} intensity={0.5} />
      <ambientLight intensity={0.4} />
      <FoldAnimator />
      <group scale={modelScale(geometry)}>
        <FlasherModel
          geometry={geometry}
          foldness={foldness}
          color={color}
          roughness={roughness}
          metalness={metalness}
        />
      </group>
    </Canvas>
  );
}
