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
  autoRotate?: boolean;
}

export function Scene({ params, foldness, color, roughness, metalness, autoRotate }: Props) {
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
      <OrbitControls autoRotate={autoRotate} autoRotateSpeed={1.2} />
      {/* Local lights only — a CDN-fetched Environment map suspends the whole
          scene (blank canvas) whenever the network is slow or offline. */}
      <hemisphereLight args={["#ffffff", "#556", 0.9]} />
      <directionalLight position={[5, -6, 8]} intensity={1.6} />
      <directionalLight position={[-6, 4, 3]} intensity={0.5} />
      <ambientLight intensity={0.35} />
      <FoldAnimator />
      <group scale={16 / params.gridDivisions}>
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
