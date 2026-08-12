"""Per-cell crease classification for the "crease pattern anatomy" reference
view (see the frontend's CreasePatternAnatomy component).

This reads what `generate_flasher` already produced (vertices/edges) and
derives, for each unit cell, which kind of crease actually touches it. It
does not recompute or duplicate any of the crease-assignment logic in
generator.py — it only inspects the public CreasePattern output, so it can
never drift from "what the generator actually assigns" and never needs the
generator's crease pattern itself to change.
"""

from __future__ import annotations

from dataclasses import dataclass

from .generator import CreasePattern

CreasedAssignments = {"mountain", "valley"}


@dataclass
class CellAnatomy:
    cx: int
    cy: int
    ring: int
    kind: str  # "hub" | "diag_main" | "diag_anti" | "pleat" | "flap"


def classify_cells(pattern: CreasePattern, n: int) -> list[CellAnatomy]:
    h = (n - 1) // 2
    grid_stride = n + 1

    def grid_id(x: int, y: int) -> int:
        return y * grid_stride + x

    def center_id(cx: int, cy: int) -> int:
        return grid_stride * grid_stride + cy * n + cx

    edge_assignment: dict[tuple[int, int], str] = {}
    for e in pattern.edges:
        key = (e.v0, e.v1) if e.v0 < e.v1 else (e.v1, e.v0)
        edge_assignment[key] = e.assignment

    def assignment(a: int, b: int) -> str:
        key = (a, b) if a < b else (b, a)
        return edge_assignment.get(key, "facet")

    cells: list[CellAnatomy] = []
    for cy in range(n):
        for cx in range(n):
            v00 = grid_id(cx, cy)
            v10 = grid_id(cx + 1, cy)
            v11 = grid_id(cx + 1, cy + 1)
            v01 = grid_id(cx, cy + 1)
            vc = center_id(cx, cy)

            if cx == h and cy == h:
                kind = "hub"
            elif assignment(v00, vc) in CreasedAssignments:
                # e_00c/e_11c ("\"-diagonal, bottom-left–top-right) is the
                # generator's "main" half of the cell's X-triangulation.
                kind = "diag_main"
            elif assignment(v10, vc) in CreasedAssignments:
                # e_10c/e_01c ("/"-diagonal) is the "anti" half.
                kind = "diag_anti"
            elif any(
                assignment(a, b) in CreasedAssignments
                for a, b in ((v00, v10), (v01, v11), (v00, v01), (v10, v11))
            ):
                kind = "pleat"
            else:
                kind = "flap"

            ring = max(abs(cx - h), abs(cy - h))
            cells.append(CellAnatomy(cx=cx, cy=cy, ring=ring, kind=kind))

    return cells
