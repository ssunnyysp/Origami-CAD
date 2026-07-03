import { create } from "zustand";
import { PRESETS } from "../model/presets";

interface AppState {
  selectedPresetId: string;
  foldness: number;
  paperColor: string;
  roughness: number;
  metalness: number;
  showCreases: boolean;
  sides: number;
  rings: number;
  spiralAngleDeg: number;
  wrapAngleDeg: number;
  radiusRatio: number;
  centralRadius: number;

  setFoldness: (t: number) => void;
  setPaperColor: (c: string) => void;
  setRoughness: (v: number) => void;
  setMetalness: (v: number) => void;
  setShowCreases: (v: boolean) => void;
  setSides: (v: number) => void;
  setRings: (v: number) => void;
  setSpiralAngleDeg: (v: number) => void;
  setWrapAngleDeg: (v: number) => void;
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
  showCreases: true,
  sides: initialPreset.sides,
  rings: initialPreset.rings,
  spiralAngleDeg: initialPreset.spiralAngleDeg,
  wrapAngleDeg: initialPreset.wrapAngleDeg,
  radiusRatio: initialPreset.radiusRatio,
  centralRadius: initialPreset.centralRadius,

  setFoldness: (t) => set({ foldness: t }),
  setPaperColor: (c) => set({ paperColor: c }),
  setRoughness: (v) => set({ roughness: v }),
  setMetalness: (v) => set({ metalness: v }),
  setShowCreases: (v) => set({ showCreases: v }),
  setSides: (v) => set({ sides: v }),
  setRings: (v) => set({ rings: v }),
  setSpiralAngleDeg: (v) => set({ spiralAngleDeg: v }),
  setWrapAngleDeg: (v) => set({ wrapAngleDeg: v }),
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
      spiralAngleDeg: preset.spiralAngleDeg,
      wrapAngleDeg: preset.wrapAngleDeg,
      radiusRatio: preset.radiusRatio,
      centralRadius: preset.centralRadius,
    });
  },
}));
