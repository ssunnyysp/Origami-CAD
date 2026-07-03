import { create } from "zustand";
import { PRESETS } from "../model/presets";

// Structural parameters (sides, rings, angles, radii, material response)
// come entirely from the selected preset — the UI exposes only model choice,
// foldness, animation, and paper color.
interface AppState {
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

  setFoldness: (t: number) => void;
  setAnimating: (v: boolean) => void;
  setPaperColor: (c: string) => void;
  selectPreset: (id: string) => void;
}

const initialPreset = PRESETS[0];

export const useAppStore = create<AppState>((set) => ({
  selectedPresetId: initialPreset.id,
  foldness: 0,
  animating: false,
  paperColor: initialPreset.paperColor,
  roughness: initialPreset.roughness,
  metalness: initialPreset.metalness,
  sides: initialPreset.sides,
  rings: initialPreset.rings,
  spiralAngleDeg: initialPreset.spiralAngleDeg,
  wrapAngleDeg: initialPreset.wrapAngleDeg,
  radiusRatio: initialPreset.radiusRatio,
  centralRadius: initialPreset.centralRadius,

  setFoldness: (t) => set({ foldness: t }),
  setAnimating: (v) => set({ animating: v }),
  setPaperColor: (c) => set({ paperColor: c }),
  selectPreset: (id) => {
    const preset = PRESETS.find((p) => p.id === id);
    if (!preset) return;
    set({
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
    });
  },
}));
