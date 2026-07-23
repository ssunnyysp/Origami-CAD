import { useMemo } from "react";
import type { CreaseAssignment, FlasherGeometry } from "../../model/types";
import type { Theme } from "../../store/useAppStore";

// Mountain folds up (yellow), valley folds down (red) — same fold-direction
// convention as the 3D crease overlay, applied uniformly to every real
// crease (including the diagonal — no crease is a special case). Facet
// edges are triangulation artifacts, not creases in the actual pattern —
// they are never drawn here, only mountain/valley/border. Border needs a
// theme-specific tone: near-black reads fine on light paper but disappears
// against a dark background.
type DrawnAssignment = Exclude<CreaseAssignment, "facet">;

const STROKES: Record<Theme, Record<DrawnAssignment, { color: string; width: number }>> = {
  light: {
    border: { color: "#0b0e14", width: 0.1 },
    mountain: { color: "#ca8a04", width: 0.07 },
    valley: { color: "#dc2626", width: 0.07 },
  },
  dark: {
    border: { color: "#edecea", width: 0.1 },
    mountain: { color: "#facc15", width: 0.07 },
    valley: { color: "#f87171", width: 0.07 },
  },
};

const DRAW_ORDER: DrawnAssignment[] = ["mountain", "valley", "border"];

interface Props {
  geometry: FlasherGeometry | null;
  theme: Theme;
  visible: boolean;
}

// Flat 2D view of the crease pattern, like a printed folding diagram.
export function PatternView({ geometry, theme, visible }: Props) {
  const strokes = STROKES[theme];
  const lines = useMemo(() => {
    if (!geometry) return null;
    const byId = new Map(geometry.pattern.vertices.map((v) => [v.id, v.position]));
    return DRAW_ORDER.map((assignment) => ({
      assignment,
      segments: geometry.pattern.edges
        .filter((e) => e.assignment === assignment)
        .map((e) => ({ id: e.id, p0: byId.get(e.v0)!, p1: byId.get(e.v1)! })),
    }));
  }, [geometry]);

  if (!lines || !geometry) return null;

  let maxAbs = 0;
  for (const v of geometry.pattern.vertices) {
    maxAbs = Math.max(maxAbs, Math.abs(v.position.x), Math.abs(v.position.y));
  }
  const half = (maxAbs || 1) + 0.6;

  return (
    <div className={`pattern-view${visible ? "" : " pattern-view--hidden"}`} aria-hidden={!visible}>
      <svg viewBox={`${-half} ${-half} ${2 * half} ${2 * half}`}>
        {/* Flip y so the pattern matches the 3D view's orientation. */}
        <g transform="scale(1,-1)">
          {lines.map(({ assignment, segments }) => (
            <g
              key={assignment}
              stroke={strokes[assignment].color}
              strokeWidth={strokes[assignment].width}
              strokeLinecap="round"
            >
              {segments.map((s) => (
                <line key={s.id} x1={s.p0.x} y1={s.p0.y} x2={s.p1.x} y2={s.p1.y} />
              ))}
            </g>
          ))}
        </g>
      </svg>
      <div className="pattern-legend">
        <span>
          <i style={{ background: strokes.mountain.color }} /> mountain
        </span>
        <span>
          <i style={{ background: strokes.valley.color }} /> valley
        </span>
      </div>
    </div>
  );
}
