import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { FlasherParams } from "../../model/types";
import { FlasherModel } from "./FlasherModel";
import { FoldAnimator } from "./FoldAnimator";

interface Props {
  params: FlasherParams;
  foldness: number;
  color: string;
  roughness: number;
  metalness: number;
}

export function Scene({ params, foldness, color, roughness, metalness }: Props) {
  // Never remount the Canvas — it blanks the view while the WebGL context and
  // scene rebuild. Instead of moving the camera per preset, the model group
  // is scale-normalized to a consistent on-screen size and the camera stays
  // fixed. The flat sheet's outer apothem grows by `pleatRatio` per ring
  // from the hub's fixed apothem of 1 (see generator.py's HUB_APOTHEM); its
  // circumradius (the true farthest extent) divides that by cos(pi/sides).
  const cameraDistance = 34;
  const outerApothem = 1 + params.rings * params.pleatRatio;
  const outerRadius = outerApothem / Math.cos(Math.PI / params.sides);

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
      <group scale={8 / outerRadius}>
        <FlasherModel
          params={params}
          foldness={foldness}
          color={color}
          roughness={roughness}
          metalness={metalness}
        />
      </group>
    </Canvas>
  );
}
