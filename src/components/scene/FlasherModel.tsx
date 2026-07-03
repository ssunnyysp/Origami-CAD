import { useMemo } from "react";
import { generateFlasher, type FlasherParams } from "../../model/flasherGenerator";
import { computeRingTransforms } from "../../model/foldEngine";
import { Ring } from "./Ring";

interface Props {
  params: FlasherParams;
  foldness: number;
  color: string;
  roughness: number;
  metalness: number;
}

export function FlasherModel({ params, foldness, color, roughness, metalness }: Props) {
  const { sides, rings, twistAngle, radiusRatio, centralRadius } = params;

  const pattern = useMemo(
    () => generateFlasher({ sides, rings, twistAngle, radiusRatio, centralRadius }),
    [sides, rings, twistAngle, radiusRatio, centralRadius],
  );
  const ringTransforms = useMemo(
    () => computeRingTransforms({ sides, rings, twistAngle, radiusRatio, centralRadius }),
    [sides, rings, twistAngle, radiusRatio, centralRadius],
  );

  return (
    <>
      {ringTransforms.map((target) => (
        <Ring
          key={target.ringIndex}
          pattern={pattern}
          ringIndex={target.ringIndex}
          target={target}
          foldness={foldness}
          color={color}
          roughness={roughness}
          metalness={metalness}
        />
      ))}
    </>
  );
}
