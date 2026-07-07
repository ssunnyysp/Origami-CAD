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
  gridDivisions: number;
  wrapPerRing: number;
  layerGapRatio: number;
  heightRatio: number;

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
    gridDivisions: preset.gridDivisions,
    wrapPerRing: preset.wrapPerRing,
    layerGapRatio: preset.layerGapRatio,
    heightRatio: preset.heightRatio,
  };
}

export const useAppStore = create<AppState>((set, get) => ({
  ready: false,
  presets: [],
  selectedPresetId: "",
  foldness: 0,
  animating: false,
  paperColor: "#d97757",
  roughness: 0.8,
  metalness: 0.02,
  gridDivisions: 8,
  wrapPerRing: 1.0,
  layerGapRatio: 0.15,
  heightRatio: 0.85,

  loadPresets: async () => {
    if (get().presets.length > 0) return;
    const presets = await fetchPresets();
    if (presets.length === 0) throw new Error("backend returned no presets");
    // First impression: open on the folded 3D form, so dragging the slider
    // unfolds it into the flat sheet.
    set({ presets, ready: true, ...applyPreset(presets[0]), foldness: 1 });
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
