import { create } from "zustand";
import type { FlasherPreset, FoldFrameInfo, FoldImportResponse } from "../model/types";
import { fetchPresets, importFold } from "../api/client";

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
  viewMode: "3d" | "pattern";
  paperColor: string;
  roughness: number;
  metalness: number;
  gridDivisions: number;
  layerGapRatio: number;
  heightRatio: number;

  // FOLD import: when patternSource is "imported", the scene renders
  // `importedGeometry` instead of the generated preset (see
  // api/useActiveGeometry.ts). Importing never discards the preset
  // params/color above, so switching back to "generated" (via selectPreset,
  // or explicitly clearing the import) resumes exactly where preset browsing
  // left off.
  patternSource: "generated" | "imported";
  importedFileName: string | null;
  importedGeometry: FoldImportResponse | null;
  importError: string | null;
  importing: boolean;

  loadPresets: () => Promise<void>;
  setFoldness: (t: number) => void;
  setAnimating: (v: boolean) => void;
  setPaperColor: (c: string) => void;
  setViewMode: (m: "3d" | "pattern") => void;
  selectPreset: (id: string) => void;
  importFoldFile: (file: File) => Promise<void>;
  selectImportedFrame: (frameIndex: number) => Promise<void>;
  clearImport: () => void;
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
  viewMode: "3d",
  paperColor: "#d97757",
  roughness: 0.8,
  metalness: 0.02,
  gridDivisions: 7,
  layerGapRatio: 0.14,
  heightRatio: 0.85,

  patternSource: "generated",
  importedFileName: null,
  importedGeometry: null,
  importError: null,
  importing: false,

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
  setViewMode: (m) => set({ viewMode: m, animating: false }),
  selectPreset: (id) => {
    const preset = get().presets.find((p) => p.id === id);
    if (!preset) return;
    set({ ...applyPreset(preset), patternSource: "generated", importError: null });
  },

  importFoldFile: async (file) => {
    set({ importing: true, importError: null });
    try {
      const text = await file.text();
      let document: unknown;
      try {
        document = JSON.parse(text);
      } catch {
        throw new Error(`"${file.name}" isn't valid JSON, so it can't be a .fold file`);
      }
      rememberImportedDocument(document);
      const geometry = await importFold(document);
      set({
        importedGeometry: geometry,
        importedFileName: file.name,
        patternSource: "imported",
        animating: false,
        foldness: geometry.foldnessSamples[geometry.foldnessSamples.length - 1] ?? 1,
        importing: false,
      });
    } catch (err) {
      set({ importing: false, importError: err instanceof Error ? err.message : String(err) });
    }
  },

  selectImportedFrame: async (frameIndex) => {
    const { importedGeometry } = get();
    if (!importedGeometry) return;
    set({ importing: true, importError: null });
    try {
      // Re-parsing from the frame list alone isn't possible client-side (the
      // raw document isn't retained after the first parse), so re-import by
      // frame index requires the original document — kept in module state
      // rather than the store proper since it's large and never rendered.
      const document = lastImportedDocument;
      if (!document) throw new Error("original file no longer available — re-upload it");
      const geometry = await importFold(document, frameIndex);
      set({
        importedGeometry: geometry,
        patternSource: "imported",
        animating: false,
        foldness: geometry.foldnessSamples[geometry.foldnessSamples.length - 1] ?? 1,
        importing: false,
      });
    } catch (err) {
      set({ importing: false, importError: err instanceof Error ? err.message : String(err) });
    }
  },

  clearImport: () => {
    lastImportedDocument = null;
    set({ importedGeometry: null, importedFileName: null, importError: null, patternSource: "generated" });
  },
}));

// The raw parsed document, kept outside the store (it can be a few MB for a
// dense imported pattern and is never itself rendered) so switching between
// a file's frames doesn't require re-uploading it.
let lastImportedDocument: unknown = null;

export function rememberImportedDocument(document: unknown): void {
  lastImportedDocument = document;
}

export type { FoldFrameInfo };
