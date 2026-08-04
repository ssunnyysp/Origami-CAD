import { useMemo } from "react";
import type { FlasherGeometry } from "../../model/types";
import type { Theme } from "../../store/useAppStore";
import { interpolatePositions } from "../../model/interpolate";
import { FlasherMesh } from "./FlasherMesh";
import { CreaseLines } from "./CreaseLines";

interface Props {
  geometry: FlasherGeometry | null;
  foldness: number;
  color: string;
  roughness: number;
  metalness: number;
  theme: Theme;
}

// The crease pattern and the full fold trajectory are solved by the Python
// backend in one request (either the generated preset's params or an
// imported FOLD file — see api/useActiveGeometry.ts); rendering any foldness
// value is just interpolation between the returned frames.
export function FlasherModel({ geometry, foldness, color, roughness, metalness, theme }: Props) {
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
      <CreaseLines
        pattern={geometry.pattern}
        positions={positions}
        foldness={foldness}
        paperColor={color}
        theme={theme}
      />
    </>
  );
}
