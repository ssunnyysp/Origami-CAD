export interface FlasherPreset {
  id: string;
  name: string;
  sides: number;
  rings: number;
  spiralAngleDeg: number;
  wrapAngleDeg: number; // 360 / sides = each ring wraps exactly one hub face further
  radiusRatio: number;
  centralRadius: number;
  paperColor: string;
  roughness: number;
  metalness: number;
}

export const PRESETS: FlasherPreset[] = [
  {
    id: "square",
    name: "Square Flasher",
    sides: 4,
    rings: 5,
    spiralAngleDeg: 20,
    wrapAngleDeg: 90,
    radiusRatio: 1.3,
    centralRadius: 1,
    paperColor: "#e8dcc8",
    roughness: 0.8,
    metalness: 0.05,
  },
  {
    id: "hex",
    name: "Hexagonal Flasher",
    sides: 6,
    rings: 5,
    spiralAngleDeg: 15,
    wrapAngleDeg: 60,
    radiusRatio: 1.28,
    centralRadius: 1,
    paperColor: "#cde0d8",
    roughness: 0.7,
    metalness: 0.05,
  },
  {
    id: "tri-tight",
    name: "Triangular Flasher (Tight Spiral)",
    sides: 3,
    rings: 6,
    spiralAngleDeg: 28,
    wrapAngleDeg: 120,
    radiusRatio: 1.24,
    centralRadius: 1,
    paperColor: "#e0c8d8",
    roughness: 0.75,
    metalness: 0.1,
  },
  {
    id: "octagon-wide",
    name: "Octagonal Flasher (Wide Rings)",
    sides: 8,
    rings: 4,
    spiralAngleDeg: 12,
    wrapAngleDeg: 45,
    radiusRatio: 1.45,
    centralRadius: 1,
    paperColor: "#c8d4e8",
    roughness: 0.6,
    metalness: 0.15,
  },
];
