import { useEffect, useMemo, useState } from "react";
import { fetchPatternAnatomy } from "../../api/client";
import { useAppStore } from "../../store/useAppStore";
import type { CellAnatomy, CellAnatomyKind, PatternAnatomy } from "../../model/types";

// Cell-by-cell view of the crease pattern, colored by what generate_flasher
// actually assigns (see backend/app/flasher/anatomy.py) — not a mockup, and
// not hand-authored data that can drift from the real pattern. Grid sizes
// are read from the app's own presets, so this only ever offers sizes the
// flasher itself can produce.

const KIND_LABEL: Record<CellAnatomyKind, string> = {
  hub: "Hub cell",
  diag_main: "Diagonal crease (main diagonal)",
  diag_anti: "Diagonal crease (anti-diagonal)",
  pleat: "Accordion pleat cell",
  flap: "Uncreased flap cell",
};

const KIND_DESC: Record<CellAnatomyKind, string> = {
  hub: "Stays flat. Every ring wraps around this cell.",
  diag_main: "Carries the region's 45° diagonal crease, bottom-left–top-right half.",
  diag_anti: "Carries the region's 45° diagonal crease, bottom-right–top-left half.",
  pleat: "At least one of its grid edges is a real mountain/valley crease — part of the accordion that compresses as the sheet folds, or a hub-wall bend.",
  flap: "No creases touch this cell at all — a flat facet flap.",
};

interface Props {
  onClose: () => void;
}

export function CreasePatternAnatomy({ onClose }: Props) {
  const presets = useAppStore((s) => s.presets);
  const sizes = useMemo(
    () => Array.from(new Set(presets.map((p) => p.gridDivisions))).sort((a, b) => a - b),
    [presets],
  );

  const [currentN, setCurrentN] = useState<number | null>(null);
  const [selected, setSelected] = useState<CellAnatomy | null>(null);
  const [showRings, setShowRings] = useState(false);
  const [showDiag, setShowDiag] = useState(true);
  const [dataByN, setDataByN] = useState<Record<number, PatternAnatomy>>({});
  const [loadingN, setLoadingN] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (currentN === null && sizes.length > 0) setCurrentN(sizes[0]);
  }, [sizes, currentN]);

  useEffect(() => {
    if (currentN === null || dataByN[currentN]) return;
    let cancelled = false;
    setLoadingN(currentN);
    setError(null);
    fetchPatternAnatomy(currentN)
      .then((data) => {
        if (cancelled) return;
        setDataByN((prev) => ({ ...prev, [currentN]: data }));
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoadingN(null);
      });
    return () => {
      cancelled = true;
    };
  }, [currentN, dataByN]);

  const data = currentN !== null ? dataByN[currentN] : undefined;

  const byCoord = useMemo(() => {
    const map = new Map<string, CellAnatomy>();
    data?.cells.forEach((c) => map.set(`${c.cx},${c.cy}`, c));
    return map;
  }, [data]);

  function changeSize(n: number) {
    setCurrentN(n);
    setSelected(null);
  }

  if (currentN === null) return null;

  const n = data?.n ?? currentN;
  const cellPx = n <= 9 ? 34 : n <= 13 ? 28 : n <= 23 ? 20 : 15;
  const total = cellPx * n + 2 * (n - 1);

  const rows: number[] = [];
  for (let cy = n - 1; cy >= 0; cy--) rows.push(cy);
  const cols: number[] = [];
  for (let cx = 0; cx < n; cx++) cols.push(cx);

  return (
    <div className="anatomy-overlay" role="dialog" aria-modal="true" aria-label="Crease pattern anatomy">
      <div className="anatomy">
        <div className="anatomy-titlebar">
          <div>
            <h1>Crease pattern anatomy</h1>
            <p className="anatomy-sub">
              Every cell of the generated flasher sheet, colored by what the generator actually
              assigns to it — computed live from the current crease pattern, not a mockup. Pick a
              grid size, hover or click a cell to see its coordinates.
            </p>
          </div>
          <button className="anatomy-close" onClick={onClose} aria-label="Close crease pattern anatomy" title="Close">
            ×
          </button>
        </div>

        <div className="anatomy-toolbar">
          <div className="anatomy-field">
            <span className="anatomy-field-label">Grid size</span>
            <div className="anatomy-sizes">
              {sizes.map((s) => (
                <button key={s} className={s === currentN ? "active" : ""} onClick={() => changeSize(s)}>
                  {s}×{s}
                </button>
              ))}
            </div>
          </div>
          <label className="anatomy-toggle">
            <input type="checkbox" checked={showRings} onChange={(e) => setShowRings(e.target.checked)} />
            Show ring index
          </label>
          <label className="anatomy-toggle">
            <input type="checkbox" checked={showDiag} onChange={(e) => setShowDiag(e.target.checked)} />
            Show diagonal guides
          </label>
        </div>

        <div className="anatomy-stage">
          <div className="anatomy-grid-card">
            {!data ? (
              <div className="anatomy-status">
                {error ? `Couldn't load: ${error}` : loadingN === currentN ? "Solving crease pattern…" : ""}
              </div>
            ) : (
              <div
                className="anatomy-grid-outer"
                style={{ gridTemplateColumns: `22px ${total}px`, gridTemplateRows: `16px ${total}px` }}
              >
                <div />
                <div className="anatomy-axis-x" style={{ gridTemplateColumns: `repeat(${n}, ${cellPx}px)` }}>
                  {cols.map((cx) => (
                    <div key={cx}>{cx}</div>
                  ))}
                </div>
                <div className="anatomy-axis-y" style={{ gridTemplateRows: `repeat(${n}, ${cellPx}px)` }}>
                  {rows.map((cy) => (
                    <div key={cy}>{cy}</div>
                  ))}
                </div>
                <div
                  className="anatomy-grid-cells"
                  style={{
                    gridTemplateColumns: `repeat(${n}, ${cellPx}px)`,
                    gridTemplateRows: `repeat(${n}, ${cellPx}px)`,
                  }}
                >
                  {rows.map((cy) =>
                    cols.map((cx) => {
                      const c = byCoord.get(`${cx},${cy}`);
                      if (!c) return null;
                      return (
                        <button
                          key={`${cx},${cy}`}
                          className={`anatomy-cell ${c.kind}${selected === c ? " selected" : ""}`}
                          style={{ width: cellPx, height: cellPx }}
                          title={`(${c.cx}, ${c.cy}) — ring ${c.ring} — ${KIND_LABEL[c.kind]}`}
                          onMouseEnter={() => setSelected(c)}
                          onFocus={() => setSelected(c)}
                          onClick={() => setSelected((prev) => (prev === c ? null : c))}
                        >
                          {c.kind === "hub" ? "H" : showRings ? c.ring : ""}
                        </button>
                      );
                    }),
                  )}
                  {showDiag && (
                    <svg className="anatomy-diagonals" viewBox={`0 0 ${total} ${total}`}>
                      <line x1={0} y1={0} x2={total} y2={total} />
                      <line x1={total} y1={0} x2={0} y2={total} />
                    </svg>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="anatomy-side">
            <div className="anatomy-panel">
              <h2>Selected cell</h2>
              <div className="anatomy-detail">
                {selected ? (
                  <>
                    <div className="anatomy-detail-coord">
                      ({selected.cx}, {selected.cy})
                    </div>
                    <div className="anatomy-detail-kind">
                      <b>{KIND_LABEL[selected.kind]}.</b> {KIND_DESC[selected.kind]}
                    </div>
                    <span className="anatomy-detail-ring">ring {selected.ring}</span>
                  </>
                ) : (
                  <div className="anatomy-detail-empty">Hover or click a cell to inspect it.</div>
                )}
              </div>
            </div>

            <div className="anatomy-panel">
              <h2>Legend</h2>
              <LegendRow swatchClass="hub" title="Hub" desc="the single central cell, stays flat" />
              <LegendRow swatchClass="diag_main" title="Diagonal — main" desc="bottom-left–top-right half" />
              <LegendRow swatchClass="diag_anti" title="Diagonal — anti" desc="bottom-right–top-left half" />
              <LegendRow swatchClass="pleat" title="Pleat" desc="touches a real mountain/valley crease" />
            </div>

            <div className="anatomy-panel">
              <h2>What the colors show</h2>
              <p className="anatomy-note">
                The <b>blue</b> and <b>orange</b> cells sit exactly on the two diagonals through the
                hub, splitting the sheet into <b>4 pinwheel-symmetric rectangular regions</b>. Every
                other non-hub cell in the current pattern touches at least one accordion pleat or hub-wall
                crease (<b>green</b>) — the design has no uncreased "flap" cells at any of these grid
                sizes, unlike an earlier hand-authored sketch of this pattern.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function LegendRow({ swatchClass, title, desc }: { swatchClass: string; title: string; desc: string }) {
  return (
    <div className="anatomy-legend-row">
      <span className={`anatomy-swatch ${swatchClass}`} />
      <span className="anatomy-legend-text">
        <b>{title}</b> — <span>{desc}</span>
      </span>
    </div>
  );
}
