import { useMemo } from "react";
import type { FlasherParams } from "../../model/types";
import { useFlasherGeometry } from "../../api/useFlasherGeometry";
import { interpolatePositions } from "../../model/interpolate";
import { FlasherMesh } from "./FlasherMesh";
import { CreaseLines } from "./CreaseLines";

interface Props {
  params: FlasherParams;
  foldness: number;
  color: string;
  roughness: number;
  metalness: number;
}

// The crease pattern and the full fold trajectory are solved by the Python
// backend in one request per parameter set; rendering any foldness value is
// just interpolation between the returned frames.
export function FlasherModel({ params, foldness, color, roughness, metalness }: Props) {
  const geometry = useFlasherGeometry(params);
  const positions = useMemo(
    () => (geometry ? interpolatePositions(geometry, foldness) : null),
    [geometry, foldness],
  );

  if (!geometry || !positions) return null; // first fetch still in flight

  return (
    <>
      <FlasherMesh
        pattern={geometry.pattern}
        positions={positions}
        color={color}
        roughness={roughness}
        metalness={metalness}
      />
      <CreaseLines pattern={geometry.pattern} positions={positions} foldness={foldness} />
    </>
  );
}
