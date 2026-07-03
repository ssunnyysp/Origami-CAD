import { useMemo } from "react";
import { generateFlasher, type FlasherParams } from "../../model/flasherGenerator";
import { computeVertexPositionsAtFoldness } from "../../model/foldEngine";
import { FlasherMesh } from "./FlasherMesh";
import { CreaseLines } from "./CreaseLines";

interface Props {
  params: FlasherParams;
  foldness: number;
  color: string;
  roughness: number;
  metalness: number;
  showCreases: boolean;
}

export function FlasherModel({ params, foldness, color, roughness, metalness, showCreases }: Props) {
  const { sides, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius } = params;

  // Topology depends only on structural params; positions also on foldness.
  const pattern = useMemo(
    () => generateFlasher({ sides, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius }),
    [sides, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius],
  );
  const positions = useMemo(
    () =>
      computeVertexPositionsAtFoldness(
        { sides, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius },
        foldness,
      ),
    [sides, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius, foldness],
  );

  return (
    <>
      <FlasherMesh
        pattern={pattern}
        positions={positions}
        color={color}
        roughness={roughness}
        metalness={metalness}
      />
      {showCreases && <CreaseLines pattern={pattern} positions={positions} />}
    </>
  );
}
