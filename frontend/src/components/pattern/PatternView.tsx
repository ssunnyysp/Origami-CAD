import { useMemo } from "react";
import type { CreaseAssignment, FlasherParams } from "../../model/types";
import { useFlasherGeometry } from "../../api/useFlasherGeometry";

// Mountain folds up (blue), valley folds down (red) — same convention as the
// 3D crease overlay. Facet edges are drawn faintly as the construction grid.
const STROKES: Record<CreaseAssignment, { color: string; width: number }> = {
  border: { color: "#2b2926", width: 0.1 },
  mountain: { color: "#3560d8", width: 0.07 },
  valley: { color: "#d84035", width: 0.07 },
  facet: { color: "#e2ddd0", width: 0.025 },
};

const DRAW_ORDER: CreaseAssignment[] = ["facet", "mountain", "valley", "border"];

// Flat 2D view of the crease pattern, like a printed folding diagram.
export function PatternView({ params }: { params: FlasherParams }) {
  const geometry = useFlasherGeometry(params);

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

  // Sized from the pattern's own vertex bounds rather than a structural
  // param — robust to any hub shape/ring count without knowing its extent
  // in advance.
  const half = useMemo(() => {
    if (!geometry) return 1;
    const reach = geometry.pattern.vertices.reduce(
      (m, v) => Math.max(m, Math.abs(v.position.x), Math.abs(v.position.y)),
      0,
    );
    return reach + 0.6;
  }, [geometry]);

  if (!lines) return null;

  return (
    <div className="pattern-view">
      <svg viewBox={`${-half} ${-half} ${2 * half} ${2 * half}`}>
        {/* Flip y so the pattern matches the 3D view's orientation. */}
        <g transform="scale(1,-1)">
          {lines.map(({ assignment, segments }) => (
            <g
              key={assignment}
              stroke={STROKES[assignment].color}
              strokeWidth={STROKES[assignment].width}
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
          <i style={{ background: "#3560d8" }} /> mountain
        </span>
        <span>
          <i style={{ background: "#d84035" }} /> valley
        </span>
      </div>
    </div>
  );
}
