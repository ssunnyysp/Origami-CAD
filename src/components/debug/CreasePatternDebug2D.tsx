import type { CreasePattern } from "../../model/types";

const COLOR_BY_ASSIGNMENT: Record<string, string> = {
  mountain: "#e04040",
  valley: "#4060e0",
  border: "#111111",
  facet: "#999999",
};

interface Props {
  pattern: CreasePattern;
  size?: number;
}

// Throwaway debug view: renders the flat crease pattern as SVG so the
// generator's output can be sanity-checked before any 3D work.
export function CreasePatternDebug2D({ pattern, size = 500 }: Props) {
  const maxRadius = Math.max(...pattern.vertices.map((v) => Math.hypot(v.position.x, v.position.y)));
  const scale = (size / 2 / maxRadius) * 0.9;
  const cx = size / 2;
  const cy = size / 2;
  const px = (x: number) => cx + x * scale;
  const py = (y: number) => cy - y * scale;

  const vertexById = new Map(pattern.vertices.map((v) => [v.id, v]));

  return (
    <svg width={size} height={size} style={{ background: "#fafafa", border: "1px solid #ccc" }}>
      {pattern.edges.map((edge) => {
        const v0 = vertexById.get(edge.v0)!;
        const v1 = vertexById.get(edge.v1)!;
        return (
          <line
            key={edge.id}
            x1={px(v0.position.x)}
            y1={py(v0.position.y)}
            x2={px(v1.position.x)}
            y2={py(v1.position.y)}
            stroke={COLOR_BY_ASSIGNMENT[edge.assignment]}
            strokeWidth={edge.assignment === "border" ? 2 : 1}
          />
        );
      })}
      {pattern.vertices.map((v) => (
        <circle key={v.id} cx={px(v.position.x)} cy={py(v.position.y)} r={2} fill="#000" />
      ))}
    </svg>
  );
}
