import { useMemo } from "react";
import type { CreaseAssignment, FlasherGeometry } from "../../model/types";
import type { Theme } from "../../store/useAppStore";

// Mountain folds up (blue), valley folds down (red) — same convention as the
// 3D crease overlay. Facet edges are drawn faintly as the construction grid.
// Border/facet need theme-specific tones: a near-black border and pale-gray
// facet grid both read fine on light paper but would go invisible (border)
// or vanish into noise (facet) against a dark background.
const STROKES: Record<Theme, Record<CreaseAssignment, { color: string; width: number }>> = {
  light: {
    border: { color: "#0b0e14", width: 0.1 },
    mountain: { color: "#2563eb", width: 0.07 },
    valley: { color: "#dc2626", width: 0.07 },
    facet: { color: "#dde1e7", width: 0.025 },
  },
  dark: {
    border: { color: "#e8eaf0", width: 0.1 },
    mountain: { color: "#5b9bff", width: 0.07 },
    valley: { color: "#f87171", width: 0.07 },
    facet: { color: "#232838", width: 0.025 },
  },
};

const DRAW_ORDER: CreaseAssignment[] = ["facet", "mountain", "valley", "border"];

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
