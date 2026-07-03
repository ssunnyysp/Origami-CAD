import { useMemo } from "react";
import { generateFlasher, type FlasherParams } from "../../model/flasherGenerator";
import { FlasherFoldSolver } from "../../model/foldSolver";
import { FlasherMesh } from "./FlasherMesh";
import { CreaseLines } from "./CreaseLines";

interface Props {
  params: FlasherParams;
  foldness: number;
  color: string;
  roughness: number;
  metalness: number;
}

export function FlasherModel({ params, foldness, color, roughness, metalness }: Props) {
  const { sides, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius } = params;

  const pattern = useMemo(
    () => generateFlasher({ sides, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius }),
    [sides, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius],
  );
  // The solver is stateful (warm-started between foldness values); a new one
  // is built whenever the pattern or fold parameters change.
  const solver = useMemo(
    () =>
      new FlasherFoldSolver(pattern, {
        sides,
        rings,
        spiralAngle,
        wrapAngle,
        radiusRatio,
        centralRadius,
      }),
    [pattern, sides, rings, spiralAngle, wrapAngle, radiusRatio, centralRadius],
  );
  const positions = useMemo(() => solver.positionsAt(foldness), [solver, foldness]);

  return (
    <>
      <FlasherMesh
        pattern={pattern}
        positions={positions}
        color={color}
        roughness={roughness}
        metalness={metalness}
      />
      <CreaseLines pattern={pattern} positions={positions} foldness={foldness} />
    </>
  );
}
