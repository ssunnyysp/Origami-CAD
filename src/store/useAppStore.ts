import { create } from "zustand";
import { PRESETS } from "../model/presets";

interface AppState {
  selectedPresetId: string;
  foldness: number;
  paperColor: string;
  roughness: number;
  metalness: number;
  sides: number;
  rings: number;
  twistAngleDeg: number;
  radiusRatio: number;
  centralRadius: number;

  setFoldness: (t: number) => void;
  setPaperColor: (c: string) => void;
  setRoughness: (v: number) => void;
  setMetalness: (v: number) => void;
  setSides: (v: number) => void;
  setRings: (v: number) => void;
  setTwistAngleDeg: (v: number) => void;
  setRadiusRatio: (v: number) => void;
  selectPreset: (id: string) => void;
}

const initialPreset = PRESETS[0];

export const useAppStore = create<AppState>((set) => ({
  selectedPresetId: initialPreset.id,
  foldness: 0,
  paperColor: initialPreset.paperColor,
  roughness: initialPreset.roughness,
  metalness: initialPreset.metalness,
  sides: initialPreset.sides,
  rings: initialPreset.rings,
  twistAngleDeg: initialPreset.twistAngleDeg,
  radiusRatio: initialPreset.radiusRatio,
  centralRadius: initialPreset.centralRadius,

  setFoldness: (t) => set({ foldness: t }),
  setPaperColor: (c) => set({ paperColor: c }),
  setRoughness: (v) => set({ roughness: v }),
  setMetalness: (v) => set({ metalness: v }),
  setSides: (v) => set({ sides: v }),
  setRings: (v) => set({ rings: v }),
  setTwistAngleDeg: (v) => set({ twistAngleDeg: v }),
  setRadiusRatio: (v) => set({ radiusRatio: v }),
  selectPreset: (id) => {
    const preset = PRESETS.find((p) => p.id === id);
    if (!preset) return;
    set({
      selectedPresetId: preset.id,
      foldness: 0,
      paperColor: preset.paperColor,
      roughness: preset.roughness,
      metalness: preset.metalness,
      sides: preset.sides,
      rings: preset.rings,
      twistAngleDeg: preset.twistAngleDeg,
      radiusRatio: preset.radiusRatio,
      centralRadius: preset.centralRadius,
    });
  },
}));
