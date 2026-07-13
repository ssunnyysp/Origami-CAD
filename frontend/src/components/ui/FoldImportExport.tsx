import { useRef, useState } from "react";
import type { FlasherGeometry } from "../../model/types";
import { exportFold } from "../../api/client";
import { interpolatePositions } from "../../model/interpolate";
import { useAppStore } from "../../store/useAppStore";

function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

interface Props {
  // Whatever is currently on screen (generated or imported) — export always
  // serializes this, not necessarily the freshly-imported geometry.
  geometry: FlasherGeometry | null;
}

// File upload (click or drag-and-drop) for .fold import, a frame picker for
// files with more than one fold state, and the "Export FOLD" action.
export function FoldImportExport({ geometry }: Props) {
  const importing = useAppStore((s) => s.importing);
  const importError = useAppStore((s) => s.importError);
  const importedFileName = useAppStore((s) => s.importedFileName);
  const importedGeometry = useAppStore((s) => s.importedGeometry);
  const patternSource = useAppStore((s) => s.patternSource);
  const importFoldFile = useAppStore((s) => s.importFoldFile);
  const selectImportedFrame = useAppStore((s) => s.selectImportedFrame);
  const clearImport = useAppStore((s) => s.clearImport);
  const foldness = useAppStore((s) => s.foldness);

  const [dragOver, setDragOver] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file) void importFoldFile(file);
  };

  const handleExport = async () => {
    if (!geometry) return;
    setExporting(true);
    setExportError(null);
    try {
      const positions = interpolatePositions(geometry, foldness);
      const doc = await exportFold(geometry.pattern, positions, "Origami CAD export");
      downloadJson(doc, "origami-cad-export.fold");
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="fold-io">
      <span className="fold-io-label">FOLD file</span>
      <div
        className={`fold-dropzone${dragOver ? " drag-over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".fold,application/json"
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
        {importing
          ? "Importing…"
          : importedFileName && patternSource === "imported"
            ? `Loaded: ${importedFileName}`
            : "Click or drop a .fold file"}
      </div>

      {importError && <p className="fold-error">{importError}</p>}

      {importedGeometry && importedGeometry.availableFrames.length > 1 && (
        <label className="control-row">
          <span>Frame</span>
          <select
            value={importedGeometry.selectedFrameIndex}
            onChange={(e) => void selectImportedFrame(Number(e.target.value))}
          >
            {importedGeometry.availableFrames.map((f) => (
              <option key={f.index} value={f.index}>
                {f.title ?? `Frame ${f.index}`}
                {f.classes.length ? ` (${f.classes.join(", ")})` : ""}
              </option>
            ))}
          </select>
        </label>
      )}

      {importedGeometry && importedGeometry.warnings.length > 0 && (
        <ul className="fold-warnings">
          {importedGeometry.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      {patternSource === "imported" && (
        <button className="action-button" onClick={clearImport}>
          Back to presets
        </button>
      )}

      <button className="action-button" onClick={() => void handleExport()} disabled={!geometry || exporting}>
        {exporting ? "Exporting…" : "Export FOLD"}
      </button>
      {exportError && <p className="fold-error">{exportError}</p>}
    </div>
  );
}
