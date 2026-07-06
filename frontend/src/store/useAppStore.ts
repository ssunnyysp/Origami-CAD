import { create } from "zustand";
import type { FlasherPreset } from "../model/types";
import { fetchPresets } from "../api/client";

// Structural parameters (sides, rings, angles, radii, material response)
// come entirely from the selected preset — the UI exposes only model choice,
// foldness, animation, and paper color. Presets live on the Python backend;
// `ready` stays false until they arrive and the first preset is applied.
interface AppState {
  ready: boolean;
  presets: FlasherPreset[];
  selectedPresetId: string;
  foldness: number;
  animating: boolean;
  paperColor: string;
  roughness: number;
  metalness: number;
  sides: number;
  rings: number;
  spiralAngleDeg: number;
  wrapAngleDeg: number;
  radiusRatio: number;
  centralRadius: number;

  loadPresets: () => Promise<void>;
  setFoldness: (t: number) => void;
  setAnimating: (v: boolean) => void;
  setPaperColor: (c: string) => void;
  selectPreset: (id: string) => void;
}

function applyPreset(preset: FlasherPreset) {
  return {
    selectedPresetId: preset.id,
    foldness: 0,
    animating: false,
    paperColor: preset.paperColor,
    roughness: preset.roughness,
    metalness: preset.metalness,
    sides: preset.sides,
    rings: preset.rings,
    spiralAngleDeg: preset.spiralAngleDeg,
    wrapAngleDeg: preset.wrapAngleDeg,
    radiusRatio: preset.radiusRatio,
    centralRadius: preset.centralRadius,
  };
}

export const useAppStore = create<AppState>((set, get) => ({
  ready: false,
  presets: [],
  selectedPresetId: "",
  foldness: 0,
  animating: false,
  paperColor: "#e8dcc8",
  roughness: 0.8,
  metalness: 0.05,
  sides: 4,
  rings: 8,
  spiralAngleDeg: 18,
  wrapAngleDeg: 90,
  radiusRatio: 1.18,
  centralRadius: 1,

  loadPresets: async () => {
    if (get().presets.length > 0) return;
    const presets = await fetchPresets();
    if (presets.length === 0) throw new Error("backend returned no presets");
    set({ presets, ready: true, ...applyPreset(presets[0]) });
  },
  setFoldness: (t) => set({ foldness: t }),
  setAnimating: (v) => set({ animating: v }),
  setPaperColor: (c) => set({ paperColor: c }),
  selectPreset: (id) => {
    const preset = get().presets.find((p) => p.id === id);
    if (!preset) return;
    set(applyPreset(preset));
  },
}));
