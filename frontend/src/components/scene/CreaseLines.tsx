import { useEffect, useMemo } from "react";
import * as THREE from "three";
import type { CreasePattern, CreaseAssignment } from "../../model/types";
import type { Theme } from "../../store/useAppStore";

// Mountain folds up (blue, matches the app's accent color), valley folds
// down (red, matches the app's error color) — same semantic pair used
// throughout the UI. Border needs a theme-specific tone: near-black reads
// fine against light paper but disappears against a dark canvas, so it
// flips to a pale tone in dark mode.
const CREASE_COLORS: Record<Theme, Partial<Record<CreaseAssignment, string>>> = {
  light: {
    mountain: "#2563eb",
    valley: "#dc2626",
    border: "#0b0e14",
  },
  dark: {
    mountain: "#5b9bff",
    valley: "#f87171",
    border: "#e8eaf0",
  },
  // facet edges are triangulation artifacts, not creases — never drawn
};

// Fallback palette used when the user's chosen paper color sits too close
// to one of the fixed crease colors above (e.g. blue paper would otherwise
// swallow the blue mountain lines). Amber/magenta sit far from both the
// default palette and each other in hue, so they stay visible against
// almost any paper color, in either theme.
const FALLBACK_CREASE_COLORS: Partial<Record<CreaseAssignment, string>> = {
  mountain: "#e0a526",
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

// CAD-style overlay: mountain (red) / valley (blue) / border (dark) crease
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

  const geometries = useMemo(() => {
    const coordsByAssignment = new Map<CreaseAssignment, number[]>();
    for (const edge of pattern.edges) {
      if (edge.assignment !== "mountain" && edge.assignment !== "valley" && edge.assignment !== "border") {
        continue;
      }
      const coords = coordsByAssignment.get(edge.assignment) ?? [];
      for (const id of [edge.v0, edge.v1]) {
        coords.push(positions[id * 3], positions[id * 3 + 1], positions[id * 3 + 2]);
      }
      coordsByAssignment.set(edge.assignment, coords);
    }
    return [...coordsByAssignment].map(([assignment, coords]) => {
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.Float32BufferAttribute(coords, 3));
      return { assignment, geom };
    });
  }, [pattern, positions]);

  useEffect(() => () => geometries.forEach(({ geom }) => geom.dispose()), [geometries]);

  if (opacity <= 0) return null;

  return (
    <>
      {geometries.map(({ assignment, geom }) => (
        <lineSegments key={assignment} geometry={geom}>
          <lineBasicMaterial color={colors[assignment]} transparent opacity={opacity} />
        </lineSegments>
      ))}
    </>
  );
}
