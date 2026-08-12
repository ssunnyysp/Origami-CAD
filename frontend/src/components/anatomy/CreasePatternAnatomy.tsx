import { useMemo, useState } from "react";
import { ANATOMY_DATA, ANATOMY_SIZES, type AnatomyCell } from "./anatomyData";

// Ported from a standalone design artifact ("Crease pattern anatomy") the
// project's author used to hand-mark the wrap-pinwheel crease pattern before
// transcribing it into generator.py — see the generator docstring / CLAUDE.md.
// This is a design/reference tool, not something the physics or geometry
// pipeline reads from: the "Design your rectangles" tab only ever produces a
// text summary the author can copy back into a session, it never mutates the
// running app's pattern.

const KIND_LABEL: Record<AnatomyCell["kind"], string> = {
  hub: "Hub cell",
  diag_main: "Diagonal crease (main diagonal)",
  diag_anti: "Diagonal crease (anti-diagonal)",
  arm: "Arm-ladder cell",
  plain: "Plain ring / radial cell",
};

const KIND_DESC: Record<AnatomyCell["kind"], string> = {
  hub: "Stays flat. Every ring wraps around this cell.",
  diag_main: "One 45° crease through the hub-side corner. Lies on the NE–SW diagonal.",
  diag_anti: "One 45° crease through the hub-side corner. Lies on the NW–SE diagonal.",
  arm: "No diagonal — a stepped polyline of edge folds (west bend, east valley pleat).",
  plain: "Only the ring-line and radial grid creases pass through; no special fold.",
};

type Rect = { cx0: number; cx1: number; cy0: number; cy1: number };
type RegionId = 1 | 2 | 3 | 4;
const REGION_COLORS: Record<RegionId, string> = { 1: "r1", 2: "r2", 3: "r3", 4: "r4" };
const REGION_LABELS: Record<RegionId, string> = { 1: "Region 1", 2: "Region 2", 3: "Region 3", 4: "Region 4" };
const REGION_IDS: RegionId[] = [1, 2, 3, 4];

type Diagonal = { x0: number; y0: number; x1: number; y1: number };
type FoldState = "mountain" | "valley";
type DesignSubMode = "rect" | "diag" | "lines";

function normalizeSel(a: { cx: number; cy: number }, b: { cx: number; cy: number }): Rect {
  return {
    cx0: Math.min(a.cx, b.cx),
    cx1: Math.max(a.cx, b.cx),
    cy0: Math.min(a.cy, b.cy),
    cy1: Math.max(a.cy, b.cy),
  };
}
function inSel(sel: Rect | null | undefined, cx: number, cy: number): boolean {
  return !!sel && cx >= sel.cx0 && cx <= sel.cx1 && cy >= sel.cy0 && cy <= sel.cy1;
}
// Rotation about the hub the generator itself uses to derive regions 2-4 from
// region 1 (see generator.py's C4 pinwheel symmetry).
function rotateVertex(x: number, y: number, n: number) {
  return { x: n - y, y: x };
}
function rotateSegment(type: "h" | "v", x: number, y: number, n: number) {
  return type === "h" ? { type: "v" as const, x: n - y, y: x } : { type: "h" as const, x: n - y - 1, y: x };
}

// Pre-filled 7×7 layout matching the shape already described when this tool
// was authored, so it's visible immediately instead of starting blank.
const INITIAL_DESIGN_7: Record<RegionId, Rect> = {
  1: { cx0: 0, cx1: 2, cy0: 3, cy1: 6 },
  2: { cx0: 3, cx1: 6, cy0: 4, cy1: 6 },
  3: { cx0: 4, cx1: 6, cy0: 0, cy1: 3 },
  4: { cx0: 0, cx1: 3, cy0: 0, cy1: 2 },
};
const INITIAL_DIAGONALS_7: Diagonal[] = [
  { x0: 3, y0: 2, x1: 5, y1: 0 },
  { x0: 5, y0: 3, x1: 7, y1: 5 },
  { x0: 4, y0: 5, x1: 2, y1: 7 },
  { x0: 2, y0: 4, x1: 0, y1: 2 },
];

interface Props {
  onClose: () => void;
}

export function CreasePatternAnatomy({ onClose }: Props) {
  const [mode, setMode] = useState<"view" | "design">("view");
  const [currentN, setCurrentN] = useState(7);
  const [selected, setSelected] = useState<AnatomyCell | null>(null);
  const [showRings, setShowRings] = useState(false);
  const [showDiag, setShowDiag] = useState(true);

  const [designState, setDesignState] = useState<Record<number, Partial<Record<RegionId, Rect>>>>({
    7: INITIAL_DESIGN_7,
  });
  const [diagonalsState, setDiagonalsState] = useState<Record<number, Diagonal[] | null>>({
    7: INITIAL_DIAGONALS_7,
  });
  const [foldLinesState, setFoldLinesState] = useState<Record<number, Record<string, FoldState>>>({});
  const [designSubMode, setDesignSubMode] = useState<DesignSubMode>("rect");
  const [pendingSel, setPendingSel] = useState<Rect | null>(null);
  const [dragStart, setDragStart] = useState<{ cx: number; cy: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [diagPick, setDiagPick] = useState<{ x: number; y: number } | null>(null);
  const [diagStatus, setDiagStatus] = useState<{ msg: string; kind?: "ok" | "err" }>({ msg: "" });
  const [copyLabel, setCopyLabel] = useState("Copy description");

  const data = ANATOMY_DATA[currentN];
  const design = useMemo(() => designState[currentN] ?? {}, [designState, currentN]);
  const diagonals = diagonalsState[currentN] ?? null;
  const foldLines = foldLinesState[currentN] ?? {};

  const byCoord = useMemo(() => {
    const map = new Map<string, AnatomyCell>();
    data.cells.forEach((c) => map.set(`${c.cx},${c.cy}`, c));
    return map;
  }, [data]);

  function changeSize(n: number) {
    setCurrentN(n);
    setSelected(null);
    setPendingSel(null);
    setDiagPick(null);
    setDiagStatus({ msg: "" });
  }

  function setDesignForN(n: number, regions: Partial<Record<RegionId, Rect>>) {
    setDesignState((prev) => ({ ...prev, [n]: regions }));
  }

  function assignRegion(id: RegionId) {
    if (!pendingSel) return;
    setDesignForN(currentN, { ...design, [id]: pendingSel });
    setPendingSel(null);
  }

  function pickVertex(x: number, y: number) {
    const n = data.n;
    if (diagPick === null) {
      setDiagPick({ x, y });
      setDiagStatus({ msg: `First point (${x}, ${y}) set — click the second point.` });
      return;
    }
    const a = diagPick;
    const b = { x, y };
    setDiagPick(null);
    if (a.x === b.x && a.y === b.y) {
      setDiagStatus({ msg: "That's the same point — try again.", kind: "err" });
      return;
    }
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    if (Math.abs(dx) !== Math.abs(dy)) {
      setDiagStatus({
        msg: `Not a 45° line: (${a.x},${a.y})–(${b.x},${b.y}) steps ${dx} in x, ${dy} in y. Pick two points with equal steps.`,
        kind: "err",
      });
      return;
    }
    const list: Diagonal[] = [{ x0: a.x, y0: a.y, x1: b.x, y1: b.y }];
    for (let i = 0; i < 3; i++) {
      const last = list[list.length - 1];
      const p0 = rotateVertex(last.x0, last.y0, n);
      const p1 = rotateVertex(last.x1, last.y1, n);
      list.push({ x0: p0.x, y0: p0.y, x1: p1.x, y1: p1.y });
    }
    setDiagonalsState((prev) => ({ ...prev, [currentN]: list }));
    setDiagStatus({ msg: "Diagonal set — mirrored to all 4 regions.", kind: "ok" });
  }

  function cycleFoldLine(type: "h" | "v", x: number, y: number) {
    const key = `${type}:${x},${y}`;
    const cur = foldLines[key];
    const next = { ...foldLines };
    if (!cur) next[key] = "mountain";
    else if (cur === "mountain") next[key] = "valley";
    else delete next[key];
    setFoldLinesState((prev) => ({ ...prev, [currentN]: next }));
  }

  function getAllFoldSegments(n: number, lines: Record<string, FoldState>) {
    const out: { type: "h" | "v"; x: number; y: number; state: FoldState }[] = [];
    for (const key in lines) {
      const state = lines[key];
      const [type, coords] = key.split(":");
      const [x0, y0] = coords.split(",").map(Number);
      let seg: { type: "h" | "v"; x: number; y: number } = { type: type as "h" | "v", x: x0, y: y0 };
      for (let i = 0; i < 4; i++) {
        out.push({ ...seg, state });
        seg = rotateSegment(seg.type, seg.x, seg.y, n);
      }
    }
    return out;
  }

  const foldSegments = getAllFoldSegments(currentN, foldLines);

  const cellPx = data.n <= 9 ? 34 : data.n <= 13 ? 28 : 24;
  const total = cellPx * data.n + 2 * (data.n - 1);
  const vpx = (v: number) => (v === 0 ? 0 : v === data.n ? total : v * (cellPx + 2) - 1);
  const vpy = (v: number) => (v === data.n ? 0 : v === 0 ? total : (data.n - v) * (cellPx + 2) - 1);

  async function handleCopy() {
    const text = summaryText;
    try {
      await navigator.clipboard.writeText(text);
      setCopyLabel("Copied");
    } catch {
      setCopyLabel("Copy failed — select the text manually");
    }
    setTimeout(() => setCopyLabel("Copy description"), 1800);
  }

  const summaryText = useMemo(() => {
    const lines: string[] = [`${data.n}×${data.n} grid — hub at (${data.h}, ${data.h})`];
    REGION_IDS.forEach((id) => {
      const r = design[id];
      if (!r) {
        lines.push(`${REGION_LABELS[id]}: not set`);
        return;
      }
      const w = r.cx1 - r.cx0 + 1;
      const h = r.cy1 - r.cy0 + 1;
      lines.push(`${REGION_LABELS[id]}: cx ${r.cx0}–${r.cx1}, cy ${r.cy0}–${r.cy1} (${w}×${h} cells)`);
    });
    if (diagonals) {
      lines.push("");
      lines.push("Diagonal creases (vertex coordinates, mirrored ×4):");
      diagonals.forEach((d, i) => {
        lines.push(`  ${i + 1}: (${d.x0}, ${d.y0})–(${d.x1}, ${d.y1})`);
      });
    } else {
      lines.push("");
      lines.push("Diagonal creases: not set");
    }
    lines.push("");
    if (foldSegments.length) {
      lines.push("Fold lines (Region 1, mirrored ×4):");
      foldSegments.forEach((s) => {
        const desc =
          s.type === "h"
            ? `H (${s.x},${s.y})–(${s.x + 1},${s.y})`
            : `V (${s.x},${s.y})–(${s.x},${s.y + 1})`;
        lines.push(`  ${desc}: ${s.state}`);
      });
    } else {
      lines.push("Fold lines: not set");
    }
    return lines.join("\n");
  }, [data, design, diagonals, foldSegments]);

  function setDesignSubModeAndReset(m: DesignSubMode) {
    setDesignSubMode(m);
    setPendingSel(null);
    setDiagPick(null);
    setDiagStatus({ msg: "" });
  }

  return (
    <div className="anatomy-overlay" role="dialog" aria-modal="true" aria-label="Crease pattern anatomy">
      <div className="anatomy" onMouseUp={() => setDragging(false)}>
        <div className="anatomy-titlebar">
          <div>
            <h1>Crease pattern anatomy</h1>
            <p className="anatomy-sub">
              {mode === "view"
                ? "Every cell of the generated flasher sheet, colored by what the generator actually assigns to it — not a mockup. Pick a grid size, hover or click a cell to see its coordinates."
                : "Drag-select a rectangle of cells, assign it to one of the 4 regions, then copy the description back into the chat."}
            </p>
          </div>
          <button className="anatomy-close" onClick={onClose} aria-label="Close crease pattern anatomy" title="Close">
            ×
          </button>
        </div>

        <div className="anatomy-tabs">
          <button className={mode === "view" ? "active" : ""} onClick={() => setMode("view")}>
            Generated pattern
          </button>
          <button className={mode === "design" ? "active" : ""} onClick={() => setMode("design")}>
            Design your rectangles
          </button>
        </div>

        <div className="anatomy-toolbar">
          <div className="anatomy-field">
            <span className="anatomy-field-label">Grid size</span>
            <div className="anatomy-sizes">
              {ANATOMY_SIZES.map((n) => (
                <button key={n} className={n === currentN ? "active" : ""} onClick={() => changeSize(n)}>
                  {n}×{n}
                </button>
              ))}
            </div>
          </div>
          {mode === "view" && (
            <>
              <label className="anatomy-toggle">
                <input type="checkbox" checked={showRings} onChange={(e) => setShowRings(e.target.checked)} />
                Show ring index
              </label>
              <label className="anatomy-toggle">
                <input type="checkbox" checked={showDiag} onChange={(e) => setShowDiag(e.target.checked)} />
                Show diagonal guides
              </label>
            </>
          )}
        </div>

        {mode === "view" ? (
          <div className="anatomy-stage">
            <div className="anatomy-grid-card">
              <AnatomyGrid
                n={data.n}
                cellPx={cellPx}
                total={total}
                renderCell={(cx, cy) => {
                  const c = byCoord.get(`${cx},${cy}`)!;
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
                }}
                overlay={
                  showDiag && (
                    <svg className="anatomy-diagonals" viewBox={`0 0 ${total} ${total}`}>
                      <line x1={0} y1={0} x2={total} y2={total} />
                      <line x1={total} y1={0} x2={0} y2={total} />
                    </svg>
                  )
                }
              />
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
                <LegendRow swatchClass="diag_main" title="Diagonal — main" desc="(NE / SW corners)" />
                <LegendRow swatchClass="diag_anti" title="Diagonal — anti" desc="(NW / SE corners)" />
                <LegendRow swatchClass="arm" title="Arm-ladder" desc="edge folds only, no diagonal" />
                <LegendRow swatchClass="plain" title="Plain" desc="ring / radial pleat only" />
              </div>

              <div className="anatomy-panel">
                <h2>What the colors show</h2>
                <p className="anatomy-note">
                  The <b>blue</b> and <b>orange</b> cells sit exactly on the two diagonals through the hub. They're
                  what splits the sheet into <b>4 pinwheel-symmetric triangular sectors</b> — the "quadrants." Each
                  sector contains one green <b>arm</b> of stepped cells running out from the hub.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="anatomy-stage">
            <div className="anatomy-grid-card">
              <div className="anatomy-subtabs">
                <button
                  className={designSubMode === "rect" ? "active" : ""}
                  onClick={() => setDesignSubModeAndReset("rect")}
                >
                  Select rectangles
                </button>
                <button
                  className={designSubMode === "diag" ? "active" : ""}
                  onClick={() => setDesignSubModeAndReset("diag")}
                >
                  Draw diagonal
                </button>
                <button
                  className={designSubMode === "lines" ? "active" : ""}
                  onClick={() => setDesignSubModeAndReset("lines")}
                >
                  Mark fold lines
                </button>
              </div>

              <AnatomyGrid
                n={data.n}
                cellPx={cellPx}
                total={total}
                renderCell={(cx, cy) => {
                  const isHub = cx === data.h && cy === data.h;
                  let cls = "plain";
                  REGION_IDS.forEach((id) => {
                    if (inSel(design[id], cx, cy)) cls = REGION_COLORS[id];
                  });
                  if (isHub) cls = "hub";
                  return (
                    <button
                      key={`${cx},${cy}`}
                      className={`anatomy-cell ${cls}${isHub ? "" : " region-editable"}${
                        inSel(pendingSel, cx, cy) ? " pending" : ""
                      }`}
                      style={{ width: cellPx, height: cellPx }}
                      title={`(${cx}, ${cy})`}
                      onMouseDown={(e) => {
                        if (isHub || designSubMode !== "rect") return;
                        e.preventDefault();
                        setDragging(true);
                        setDragStart({ cx, cy });
                        setPendingSel(normalizeSel({ cx, cy }, { cx, cy }));
                      }}
                      onMouseEnter={() => {
                        if (dragging && dragStart && designSubMode === "rect") {
                          setPendingSel(normalizeSel(dragStart, { cx, cy }));
                        }
                      }}
                    >
                      {isHub ? "H" : ""}
                    </button>
                  );
                }}
                overlay={
                  <>
                    {diagonals && (
                      <svg className="anatomy-diagonals anatomy-diag-lines" viewBox={`0 0 ${total} ${total}`}>
                        {diagonals.map((d, i) => (
                          <line key={i} x1={vpx(d.x0)} y1={vpy(d.y0)} x2={vpx(d.x1)} y2={vpy(d.y1)} />
                        ))}
                      </svg>
                    )}
                    {designSubMode === "diag" && (
                      <div className="anatomy-vtx-layer">
                        {Array.from({ length: data.n + 1 }).map((_, vy) =>
                          Array.from({ length: data.n + 1 }).map((_, vx) => (
                            <button
                              key={`${vx},${vy}`}
                              className={`anatomy-vtx-dot${diagPick && diagPick.x === vx && diagPick.y === vy ? " picked" : ""}`}
                              style={{ left: vpx(vx), top: vpy(vy) }}
                              title={`(${vx}, ${vy})`}
                              onClick={(e) => {
                                e.stopPropagation();
                                pickVertex(vx, vy);
                              }}
                            />
                          )),
                        )}
                      </div>
                    )}
                    {foldSegments.length > 0 && (
                      <svg className="anatomy-diagonals anatomy-fold-lines" viewBox={`0 0 ${total} ${total}`}>
                        {foldSegments.map((s, i) =>
                          s.type === "h" ? (
                            <line
                              key={i}
                              className={s.state}
                              x1={vpx(s.x)}
                              y1={vpy(s.y)}
                              x2={vpx(s.x + 1)}
                              y2={vpy(s.y)}
                            />
                          ) : (
                            <line
                              key={i}
                              className={s.state}
                              x1={vpx(s.x)}
                              y1={vpy(s.y)}
                              x2={vpx(s.x)}
                              y2={vpy(s.y + 1)}
                            />
                          ),
                        )}
                      </svg>
                    )}
                    {designSubMode === "lines" &&
                      (!design[1] ? (
                        <div className="anatomy-seg-msg">Assign Region 1 first (Select rectangles tab).</div>
                      ) : (
                        <FoldLineLayer
                          r1={design[1]!}
                          vpx={vpx}
                          vpy={vpy}
                          foldLines={foldLines}
                          onToggle={cycleFoldLine}
                        />
                      ))}
                  </>
                }
              />
            </div>

            <div className="anatomy-side">
              {designSubMode === "rect" && (
                <>
                  <div className="anatomy-panel">
                    <h2>1. Drag to select</h2>
                    <p className="anatomy-note">
                      Click a cell and drag to select a rectangle, then assign it below. The gold cell is the fixed
                      hub, for reference — it can't be reassigned.
                    </p>
                  </div>
                  <div className="anatomy-panel">
                    <h2>2. Assign selection</h2>
                    <div className="anatomy-region-palette">
                      {REGION_IDS.map((id) => (
                        <button
                          key={id}
                          className="anatomy-region-btn"
                          disabled={!pendingSel}
                          onClick={() => assignRegion(id)}
                        >
                          <span className={`anatomy-region-swatch ${REGION_COLORS[id]}`} />
                          <span>{REGION_LABELS[id]}</span>
                          <span className="anatomy-r-note">{design[id] ? "set" : "empty"}</span>
                        </button>
                      ))}
                    </div>
                    <div className="anatomy-util-row">
                      <button className="anatomy-util-btn" onClick={() => setPendingSel(null)}>
                        Clear selection
                      </button>
                      <button
                        className="anatomy-util-btn"
                        onClick={() => {
                          setDesignForN(currentN, {});
                          setPendingSel(null);
                        }}
                      >
                        Reset all
                      </button>
                    </div>
                  </div>
                </>
              )}

              {designSubMode === "diag" && (
                <div className="anatomy-panel">
                  <h2>Draw the diagonal</h2>
                  <p className="anatomy-note">
                    Click one grid vertex (dot), then a second, to draw one diagonal crease. It must be a clean 45°
                    line (equal steps in x and y). The other 3 are filled in automatically by rotating yours 90°
                    around the hub — same rotation the generator itself uses.
                  </p>
                  <div className={`anatomy-diag-status${diagStatus.kind ? ` ${diagStatus.kind}` : ""}`}>
                    {diagStatus.msg}
                  </div>
                  <div className="anatomy-util-row">
                    <button
                      className="anatomy-util-btn"
                      onClick={() => {
                        setDiagonalsState((prev) => ({ ...prev, [currentN]: null }));
                        setDiagPick(null);
                        setDiagStatus({ msg: "" });
                      }}
                    >
                      Clear diagonal
                    </button>
                  </div>
                </div>
              )}

              {designSubMode === "lines" && (
                <div className="anatomy-panel">
                  <h2>Mark fold lines</h2>
                  <p className="anatomy-note">
                    Only Region 1's grid lines are markable — click a segment to cycle none → mountain → valley →
                    none. The other 3 regions are filled in automatically by the same 90° rotation as the diagonal.
                  </p>
                  <div className="anatomy-line-legend">
                    <span>
                      <i className="mountain" /> mountain
                    </span>
                    <span>
                      <i className="valley" /> valley
                    </span>
                  </div>
                  <div className="anatomy-util-row">
                    <button
                      className="anatomy-util-btn"
                      onClick={() => setFoldLinesState((prev) => ({ ...prev, [currentN]: {} }))}
                    >
                      Clear fold lines
                    </button>
                  </div>
                </div>
              )}

              <div className="anatomy-panel">
                <h2>3. Copy back to chat</h2>
                <pre className="anatomy-summary">{summaryText}</pre>
                <button className="anatomy-copy-btn" onClick={handleCopy}>
                  {copyLabel}
                </button>
              </div>
            </div>
          </div>
        )}
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

function AnatomyGrid({
  n,
  cellPx,
  total,
  renderCell,
  overlay,
}: {
  n: number;
  cellPx: number;
  total: number;
  renderCell: (cx: number, cy: number) => React.ReactNode;
  overlay?: React.ReactNode;
}) {
  const rows: number[] = [];
  for (let cy = n - 1; cy >= 0; cy--) rows.push(cy);
  const cols: number[] = [];
  for (let cx = 0; cx < n; cx++) cols.push(cx);

  return (
    <div className="anatomy-grid-outer" style={{ gridTemplateColumns: `22px ${total}px`, gridTemplateRows: `16px ${total}px` }}>
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
        style={{ gridTemplateColumns: `repeat(${n}, ${cellPx}px)`, gridTemplateRows: `repeat(${n}, ${cellPx}px)` }}
      >
        {rows.map((cy) => cols.map((cx) => renderCell(cx, cy)))}
        {overlay}
      </div>
    </div>
  );
}

function FoldLineLayer({
  r1,
  vpx,
  vpy,
  foldLines,
  onToggle,
}: {
  r1: Rect;
  vpx: (v: number) => number;
  vpy: (v: number) => number;
  foldLines: Record<string, FoldState>;
  onToggle: (type: "h" | "v", x: number, y: number) => void;
}) {
  const hSegs: { x: number; y: number }[] = [];
  for (let y = r1.cy0; y <= r1.cy1 + 1; y++) {
    for (let x = r1.cx0; x <= r1.cx1; x++) hSegs.push({ x, y });
  }
  const vSegs: { x: number; y: number }[] = [];
  for (let x = r1.cx0; x <= r1.cx1 + 1; x++) {
    for (let y = r1.cy0; y <= r1.cy1; y++) vSegs.push({ x, y });
  }
  return (
    <div className="anatomy-seg-layer">
      {hSegs.map(({ x, y }) => {
        const key = `h:${x},${y}`;
        const state = foldLines[key];
        return (
          <button
            key={key}
            className={`anatomy-seg-btn${state ? ` ${state}` : ""}`}
            style={{ left: vpx(x), top: vpy(y) - 3, width: vpx(x + 1) - vpx(x), height: 6 }}
            title={`(${x},${y})–(${x + 1},${y})`}
            onClick={() => onToggle("h", x, y)}
          />
        );
      })}
      {vSegs.map(({ x, y }) => {
        const key = `v:${x},${y}`;
        const state = foldLines[key];
        return (
          <button
            key={key}
            className={`anatomy-seg-btn${state ? ` ${state}` : ""}`}
            style={{ left: vpx(x) - 3, top: vpy(y + 1), width: 6, height: vpy(y) - vpy(y + 1) }}
            title={`(${x},${y})–(${x},${y + 1})`}
            onClick={() => onToggle("v", x, y)}
          />
        );
      })}
    </div>
  );
}
