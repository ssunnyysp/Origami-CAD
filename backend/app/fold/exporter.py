"""Internal CreasePattern -> FOLD conversion (the export direction).

Writes two frames: frame 0 is the flat crease pattern (FOLD's
"creasePattern" class), and file_frames[0] is the current folded 3-D pose
("foldedForm"), inheriting topology from frame 0 via frame_parent/
frame_inherit so the flat mesh data isn't duplicated. This is exactly the
frame-per-fold-state mechanism the FOLD spec intends for representing a
design plus one of its fold states in a single file, and it's what makes the
output round-trip: re-importing frame 0 reconstructs the same flat pattern.
"""

from __future__ import annotations

from ..schemas import CreasePatternOut

_ASSIGNMENT_MAP = {"mountain": "M", "valley": "V", "border": "B", "facet": "F"}


def build_fold_document(pattern: CreasePatternOut, positions: list[float], title: str) -> dict:
    by_id = {v.id: v for v in pattern.vertices}
    n = max(by_id) + 1 if by_id else 0
    if any(i not in by_id for i in range(n)):
        raise ValueError("pattern vertex ids must be contiguous, 0..N-1")
    if len(positions) != n * 3:
        raise ValueError(f"positions must have {n * 3} floats (xyz per vertex), got {len(positions)}")

    vertices_coords = [[by_id[i].position["x"], by_id[i].position["y"]] for i in range(n)]
    folded_coords = [[positions[3 * i], positions[3 * i + 1], positions[3 * i + 2]] for i in range(n)]

    edges_by_id = {e.id: e for e in pattern.edges}
    ne = max(edges_by_id) + 1 if edges_by_id else 0
    edges_vertices = [[edges_by_id[i].v0, edges_by_id[i].v1] for i in range(ne)]
    edges_assignment = [_ASSIGNMENT_MAP.get(edges_by_id[i].assignment, "U") for i in range(ne)]

    faces_by_id = {f.id: f for f in pattern.faces}
    nf = max(faces_by_id) + 1 if faces_by_id else 0
    faces_vertices = [faces_by_id[i].vertexIds for i in range(nf)]

    return {
        "file_spec": 1.1,
        "file_creator": "Origami CAD (https://github.com/ssunnyysp/Origami-CAD)",
        "file_title": title,
        "file_classes": ["singleModel"],
        "frame_title": f"{title} — flat crease pattern",
        "frame_classes": ["creasePattern"],
        "frame_attributes": ["2D"],
        "vertices_coords": vertices_coords,
        "edges_vertices": edges_vertices,
        "edges_assignment": edges_assignment,
        "faces_vertices": faces_vertices,
        "file_frames": [
            {
                "frame_parent": 0,
                "frame_inherit": True,
                "frame_title": f"{title} — folded state",
                "frame_classes": ["foldedForm"],
                "frame_attributes": ["3D"],
                "vertices_coords": folded_coords,
            }
        ],
    }
