import { useEffect, useLayoutEffect, useMemo } from "react";
import * as THREE from "three";
import type { CreasePattern, CreaseAssignment } from "../../model/types";
import type { Theme } from "../../store/useAppStore";

// Mountain folds up (yellow), valley folds down (red) — this pair is the
// project's explicit fold-direction convention: yellow creases fold one
// way, red the other, uniformly, everywhere (including the diagonal — no
// crease is a special case). Border needs a theme-specific tone: near-black
// reads fine against light paper but disappears against a dark canvas, so
// it flips to a pale tone in dark mode.
const CREASE_COLORS: Record<Theme, Partial<Record<CreaseAssignment, string>>> = {
  light: {
    mountain: "#ca8a04",
    valley: "#dc2626",
    border: "#0b0e14",
  },
  dark: {
    mountain: "#facc15",
    valley: "#f87171",
    border: "#edecea",
  },
  // facet edges are triangulation artifacts, not creases — never drawn
};

// Fallback palette used when the user's chosen paper color sits too close
// to one of the fixed crease colors above (e.g. yellow paper would otherwise
// swallow the yellow mountain lines). Blue/magenta sit far from both the
// default yellow/red palette and each other in hue, so they stay visible
// against almost any paper color, in either theme.
const FALLBACK_CREASE_COLORS: Partial<Record<CreaseAssignment, string>> = {
  mountain: "#2563eb",
  valley: "#b0289e",
};

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

// Perceptual-ish distance; cheap and good enough to decide "too close to
// tell apart" for a UI contrast fallback.
function colorDistance(a: string, b: string): number {
  const [ar, ag, ab] = hexToRgb(a);
  const [br, bg, bb] = hexToRgb(b);
  return Math.sqrt((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2);
}

const CONTRAST_THRESHOLD = 90; // out of ~441 max possible distance

interface Props {
  pattern: CreasePattern;
  positions: Float32Array; // xyz triples indexed by vertex id
  foldness: number;
  paperColor: string;
  theme: Theme;
}

// CAD-style overlay: mountain (yellow) / valley (red) / border (dark) crease
// lines, fading out as the model folds so the stowed form reads as plain
// paper rather than a wireframe.
export function CreaseLines({ pattern, positions, foldness, paperColor, theme }: Props) {
  const opacity = Math.max(0, 1 - foldness * 1.5);
  const colors = useMemo(() => {
    const base = CREASE_COLORS[theme];
    const tooClose = (["mountain", "valley"] as const).some(
      (k) => colorDistance(paperColor, base[k]!) < CONTRAST_THRESHOLD,
    );
    return tooClose ? { ...base, ...FALLBACK_CREASE_COLORS } : base;
  }, [paperColor, theme]);

  // Endpoint vertex ids per assignment, and a geometry allocated once for each.
  // Both depend only on the PATTERN — keying them on `positions` used to
  // rebuild every line geometry on every foldness change, and (worse) it did so
  // even while the overlay was fully faded out, since the opacity early-return
  // sits below these hooks.
  const groups = useMemo(() => {
    const idsByAssignment = new Map<CreaseAssignment, number[]>();
    for (const edge of pattern.edges) {
      if (edge.assignment !== "mountain" && edge.assignment !== "valley" && edge.assignment !== "border") {
        continue;
      }
      const ids = idsByAssignment.get(edge.assignment) ?? [];
      ids.push(edge.v0, edge.v1);
      idsByAssignment.set(edge.assignment, ids);
    }
    return [...idsByAssignment].map(([assignment, ids]) => {
      const order = new Uint32Array(ids);
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(order.length * 3), 3));
      return { assignment, order, geom };
    });
  }, [pattern]);

  useEffect(() => () => groups.forEach(({ geom }) => geom.dispose()), [groups]);

  const visible = opacity > 0;
  useLayoutEffect(() => {
    if (!visible) return; // nothing to draw — don't pay for the update
    for (const { order, geom } of groups) {
      const attr = geom.getAttribute("position") as THREE.BufferAttribute;
      const dst = attr.array as Float32Array;
      for (let i = 0; i < order.length; i++) {
        const src = order[i] * 3;
        const out = i * 3;
        dst[out] = positions[src];
        dst[out + 1] = positions[src + 1];
        dst[out + 2] = positions[src + 2];
      }
      attr.needsUpdate = true;
      geom.computeBoundingSphere();
    }
  }, [groups, positions, visible]);

  if (!visible) return null;

  return (
    <>
      {groups.map(({ assignment, geom }) => (
        <lineSegments key={assignment} geometry={geom}>
          <lineBasicMaterial color={colors[assignment]} transparent opacity={opacity} />
        </lineSegments>
      ))}
    </>
  );
}
