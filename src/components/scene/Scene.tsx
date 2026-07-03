import { Canvas } from "@react-three/fiber";
import { OrbitControls, Environment, PerspectiveCamera } from "@react-three/drei";
import type { FlasherParams } from "../../model/flasherGenerator";
import { FlasherModel } from "./FlasherModel";

interface Props {
  params: FlasherParams;
  foldness: number;
  color: string;
  roughness: number;
  metalness: number;
  autoRotate?: boolean;
}

export function Scene({ params, foldness, color, roughness, metalness, autoRotate }: Props) {
  const outerRadius = params.centralRadius * Math.pow(params.radiusRatio, params.rings);
  const cameraDistance = outerRadius * 3.2;

  return (
    <Canvas key={outerRadius}>
      <PerspectiveCamera makeDefault position={[0, 0, cameraDistance]} fov={45} />
      <OrbitControls autoRotate={autoRotate} autoRotateSpeed={1.2} />
      <Environment preset="studio" />
      <ambientLight intensity={0.4} />
      <FlasherModel
        params={params}
        foldness={foldness}
        color={color}
        roughness={roughness}
        metalness={metalness}
      />
    </Canvas>
  );
}
