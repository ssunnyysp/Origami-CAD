"""FOLD -> internal CreasePattern conversion (the import direction).

Reuses the `Vertex`/`Edge`/`Face`/`CreasePattern` dataclasses from
`app.flasher.generator` purely as data shapes (this module never calls
`generate_flasher` and never touches generator.py/solver.py) so that an
imported pattern is a drop-in `CreasePattern` everywhere the app already
expects one — same `CreasePatternOut.from_pattern` serialization, same
frontend rendering code.

A FOLD file's `faces_vertices` are arbitrary polygons; our internal model
(like the flasher generator) always works in triangles, so any face with more
than 3 vertices is fan-triangulated here. That's exact for convex faces (the
overwhelming majority of authored crease patterns) and a known, documented
approximation for concave ones.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from ..flasher.generator import CreasePattern, Edge, Face, Vertex
from .errors import FoldValidationError
from .generic_solver import solve_sweep_generic
from .spec import ResolvedFrame, default_frame_index, describe_frames, resolve_frames

_ASSIGNMENT_MAP = {"M": "mountain", "V": "valley", "B": "border", "F": "facet"}


def _as_int(value, context: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise FoldValidationError(f"{context} must be an integer, got {value!r}")


def _as_float(value, context: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise FoldValidationError(f"{context} must be a number, got {value!r}")


@dataclass
class FrameConversion:
    pattern: CreasePattern
    is_flat: bool
    positions3d: list[float]  # xyz flat array, vertex-id order
    warnings: list[str] = field(default_factory=list)


def _looks_flat(classes: list[str], attributes: list[str], coords3d: list[tuple[float, float, float]]) -> bool:
    if "creasePattern" in classes:
        return True
    if "foldedForm" in classes or "3D" in attributes:
        return False
    if "2D" in attributes:
        return True
    return all(abs(z) < 1e-6 for _, _, z in coords3d)


def frame_to_pattern(frame: ResolvedFrame) -> FrameConversion:
    data = frame.data
    warnings: list[str] = []

    coords_raw = data.get("vertices_coords")
    if not isinstance(coords_raw, list) or len(coords_raw) == 0:
        raise FoldValidationError("FOLD frame has no vertices_coords")

    coords3d: list[tuple[float, float, float]] = []
    for i, c in enumerate(coords_raw):
        if c is None:
            warnings.append(f"vertices_coords[{i}] is null; placed at the origin")
            coords3d.append((0.0, 0.0, 0.0))
            continue
        if not isinstance(c, (list, tuple)) or len(c) < 2:
            raise FoldValidationError(f"vertices_coords[{i}] must be an array of at least 2 numbers")
        x = _as_float(c[0], f"vertices_coords[{i}][0]")
        y = _as_float(c[1], f"vertices_coords[{i}][1]")
        z = _as_float(c[2], f"vertices_coords[{i}][2]") if len(c) >= 3 else 0.0
        coords3d.append((x, y, z))
    n_vertices = len(coords3d)

    edges_vertices_raw = data.get("edges_vertices")
    if not isinstance(edges_vertices_raw, list):
        raise FoldValidationError("FOLD frame has no edges_vertices")

    assignments_raw = data.get("edges_assignment")
    if assignments_raw is not None:
        if not isinstance(assignments_raw, list) or len(assignments_raw) != len(edges_vertices_raw):
            raise FoldValidationError("edges_assignment must be an array the same length as edges_vertices")
    else:
        warnings.append("no edges_assignment in file; all edges treated as flat/unassigned")

    edges: list[Edge] = []
    edge_lookup: dict[tuple[int, int], int] = {}
    unknown_codes_seen: set[str] = set()

    for idx, pair in enumerate(edges_vertices_raw):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise FoldValidationError(f"edges_vertices[{idx}] must be a pair of vertex indices")
        a = _as_int(pair[0], f"edges_vertices[{idx}][0]")
        b = _as_int(pair[1], f"edges_vertices[{idx}][1]")
        if not (0 <= a < n_vertices) or not (0 <= b < n_vertices):
            raise FoldValidationError(f"edges_vertices[{idx}] references an out-of-range vertex")

        assignment = "facet"
        if assignments_raw is not None:
            code = assignments_raw[idx]
            if code in _ASSIGNMENT_MAP:
                assignment = _ASSIGNMENT_MAP[code]
            else:
                unknown_codes_seen.add(str(code))

        edge_id = len(edges)
        edges.append(Edge(id=edge_id, v0=a, v1=b, assignment=assignment))
        key = (a, b) if a < b else (b, a)
        edge_lookup[key] = edge_id

    if unknown_codes_seen:
        warnings.append(
            "unsupported edges_assignment code(s) "
            + ", ".join(sorted(unknown_codes_seen))
            + " present; treated as unassigned/flat"
        )

    def get_or_create_edge(a: int, b: int) -> int:
        key = (a, b) if a < b else (b, a)
        existing = edge_lookup.get(key)
        if existing is not None:
            return existing
        edge_id = len(edges)
        edges.append(Edge(id=edge_id, v0=a, v1=b, assignment="facet"))
        edge_lookup[key] = edge_id
        return edge_id

    faces_raw = data.get("faces_vertices")
    faces: list[Face] = []
    if not faces_raw:
        warnings.append("no faces_vertices in file; only the crease/edge graph will render, not a solid mesh")
    else:
        if not isinstance(faces_raw, list):
            raise FoldValidationError("faces_vertices must be an array")
        for fidx, poly in enumerate(faces_raw):
            if not isinstance(poly, list) or len(poly) < 3:
                raise FoldValidationError(f"faces_vertices[{fidx}] must have at least 3 vertices")
            ids = [_as_int(v, f"faces_vertices[{fidx}]") for v in poly]
            for v in ids:
                if not (0 <= v < n_vertices):
                    raise FoldValidationError(f"faces_vertices[{fidx}] references an out-of-range vertex")
            # Fan-triangulate from ids[0] — exact for convex faces (the
            # normal case for crease-pattern polygons); a concave imported
            # face can produce visibly wrong triangles, a known limitation.
            for i in range(1, len(ids) - 1):
                a, b, c = ids[0], ids[i], ids[i + 1]
                e_ab = get_or_create_edge(a, b)
                e_bc = get_or_create_edge(b, c)
                e_ca = get_or_create_edge(c, a)
                faces.append(
                    Face(id=len(faces), vertex_ids=[a, b, c], edge_ids=[e_ab, e_bc, e_ca], ring_index=0)
                )

    # Face adjacency, same shape as the generator's, then a BFS "ring" depth
    # from face 0 standing in for the flasher generator's taxicab ring_index
    # (which has no meaning for an arbitrary imported topology) — purely
    # cosmetic (pattern-view coloring), not used by the generic solver.
    faces_by_edge: dict[int, list[int]] = {}
    for f in faces:
        for e in f.edge_ids:
            faces_by_edge.setdefault(e, []).append(f.id)
    adjacency = [{"faceId": f.id, "neighbors": []} for f in faces]
    for e, fids in faces_by_edge.items():
        if len(fids) != 2:
            continue
        fa, fb = fids
        adjacency[fa]["neighbors"].append({"faceId": fb, "sharedEdgeId": e})
        adjacency[fb]["neighbors"].append({"faceId": fa, "sharedEdgeId": e})

    if faces:
        depth = [-1] * len(faces)
        depth[0] = 0
        q = deque([0])
        while q:
            cur = q.popleft()
            for nb in adjacency[cur]["neighbors"]:
                nid = nb["faceId"]
                if depth[nid] == -1:
                    depth[nid] = depth[cur] + 1
                    q.append(nid)
        for f in faces:
            f.ring_index = depth[f.id] if depth[f.id] != -1 else 0

    vertices = [Vertex(id=i, position=(coords3d[i][0], coords3d[i][1])) for i in range(n_vertices)]
    pattern = CreasePattern(
        vertices=vertices,
        edges=edges,
        faces=faces,
        adjacency=adjacency,
        ring_count=max((f.ring_index for f in faces), default=0),
        sides=0,  # not a meaningful concept for an arbitrary imported pattern
    )

    flat = _looks_flat(frame.classes, frame.attributes, coords3d)
    positions3d_flat = [c for xyz in coords3d for c in xyz]
    return FrameConversion(pattern=pattern, is_flat=flat, positions3d=positions3d_flat, warnings=warnings)


@dataclass
class FoldImportResult:
    pattern: CreasePattern
    foldness_samples: list[float]
    frames: list[list[float]]
    available_frames: list[dict]
    selected_frame_index: int
    warnings: list[str]


def import_fold_document(document: dict, frame_index: int | None) -> FoldImportResult:
    resolved = resolve_frames(document)
    available = describe_frames(resolved)

    if frame_index is None:
        selected = default_frame_index(resolved)
    elif 0 <= frame_index < len(resolved):
        selected = frame_index
    else:
        raise FoldValidationError(
            f"frameIndex {frame_index} is out of range; this file has {len(resolved)} frame(s)"
        )

    conversion = frame_to_pattern(resolved[selected])
    warnings = list(conversion.warnings)

    if conversion.is_flat:
        if conversion.pattern.faces:
            # Best-effort animation: the file only gives us a flat crease
            # pattern, so we drive our own generic mountain/valley solver
            # from it, same as a procedurally-generated flasher.
            samples, frames = solve_sweep_generic(conversion.pattern)
        else:
            samples, frames = [0.0], [conversion.positions3d]
            warnings.append("no faces to fold — showing the flat crease pattern only")
    else:
        # The file's chosen frame is already a folded 3-D state and there's
        # no separate flat frame to fold *from* — inventing a plausible
        # unfold/fold trajectory would require solving the (much harder)
        # inverse flattening problem, which is out of scope. Render the given
        # pose statically instead of guessing.
        samples, frames = [0.0, 1.0], [conversion.positions3d, conversion.positions3d]
        warnings.append(
            "this frame is already a folded 3-D state with no separate flat crease pattern in the "
            "file; showing it as a static pose instead of an invented fold animation"
        )

    return FoldImportResult(
        pattern=conversion.pattern,
        foldness_samples=samples,
        frames=frames,
        available_frames=available,
        selected_frame_index=selected,
        warnings=warnings,
    )
