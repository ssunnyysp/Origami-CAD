export interface FlasherPreset {
  id: string;
  name: string;
  sides: number;
  rings: number;
  twistAngleDeg: number;
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
    rings: 3,
    twistAngleDeg: 35,
    radiusRatio: 1.35,
    centralRadius: 1,
    paperColor: "#e8dcc8",
    roughness: 0.8,
    metalness: 0.05,
  },
  {
    id: "hex",
    name: "Hexagonal Flasher",
    sides: 6,
    rings: 3,
    twistAngleDeg: 45,
    radiusRatio: 1.4,
    centralRadius: 1,
    paperColor: "#cde0d8",
    roughness: 0.7,
    metalness: 0.05,
  },
  {
    id: "tri-tight",
    name: "Triangular Flasher (Tight Twist)",
    sides: 3,
    rings: 4,
    twistAngleDeg: 20,
    radiusRatio: 1.25,
    centralRadius: 1,
    paperColor: "#e0c8d8",
    roughness: 0.75,
    metalness: 0.1,
  },
  {
    id: "octagon-wide",
    name: "Octagonal Flasher (Wide Rings)",
    sides: 8,
    rings: 2,
    twistAngleDeg: 55,
    radiusRatio: 1.7,
    centralRadius: 1,
    paperColor: "#c8d4e8",
    roughness: 0.6,
    metalness: 0.15,
  },
];
