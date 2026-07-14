"""FOLD document structure: frame resolution (frame_parent/frame_inherit) and
frame bookkeeping, kept separate from the geometry conversion in importer.py.

Per the FOLD spec (https://github.com/edemaine/fold/blob/main/doc/spec.md),
the top-level JSON object IS frame 0 (the "key frame"). `file_frames` holds
any additional frames, each of which may set `frame_parent` (default: 0, our
own leniency — the spec allows it to be absent when there's an obvious single
parent) and `frame_inherit` (if true, any of the geometry-bearing keys below
that are missing on the child are copied from the resolved parent). This is
how a file represents e.g. a crease pattern frame plus one or more folded-form
frames without repeating unchanged topology in every frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import FoldValidationError

# Keys a child frame may omit and inherit from its resolved parent.
_INHERITABLE_KEYS = (
    "vertices_coords",
    "vertices_vertices",
    "vertices_faces",
    "edges_vertices",
    "edges_faces",
    "edges_assignment",
    "edges_foldAngle",
    "edges_length",
    "faces_vertices",
    "faces_edges",
    "frame_unit",
)


@dataclass
class ResolvedFrame:
    index: int
    data: dict  # fully inheritance-resolved frame dict
    title: str | None
    classes: list[str] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)


def resolve_frames(document: dict) -> list[ResolvedFrame]:
    if not isinstance(document, dict):
        raise FoldValidationError("A FOLD file must be a single JSON object")

    raw_extra = document.get("file_frames", [])
    if not isinstance(raw_extra, list):
        raise FoldValidationError("file_frames must be an array of frame objects")

    raw_frames: list[dict] = [document, *raw_extra]
    resolved: list[ResolvedFrame] = []

    for idx, raw in enumerate(raw_frames):
        if not isinstance(raw, dict):
            raise FoldValidationError(f"file_frames[{idx - 1}] must be an object")

        data = dict(raw)
        if idx > 0:
            # Lenient default: treat a missing frame_inherit as true and a
            # missing frame_parent as 0 (the key frame) — real-world FOLD
            # files in the wild often omit both when there's only one
            # sensible parent, even though the spec's own default for
            # frame_inherit is false.
            inherit = raw.get("frame_inherit", True)
            if inherit:
                parent_idx = raw.get("frame_parent", 0)
                if not isinstance(parent_idx, int) or not (0 <= parent_idx < idx):
                    raise FoldValidationError(
                        f"file_frames[{idx - 1}] has an invalid frame_parent ({parent_idx!r}); "
                        f"must be the index of an earlier frame"
                    )
                parent_data = resolved[parent_idx].data
                for key in _INHERITABLE_KEYS:
                    if key not in data and key in parent_data:
                        data[key] = parent_data[key]

        resolved.append(
            ResolvedFrame(
                index=idx,
                data=data,
                title=data.get("frame_title"),
                classes=list(data.get("frame_classes") or []),
                attributes=list(data.get("frame_attributes") or []),
            )
        )

    return resolved


def default_frame_index(frames: list[ResolvedFrame]) -> int:
    """Prefer the flat crease-pattern frame when the file distinguishes one;
    otherwise the key frame (index 0), matching "load the base frame by
    default"."""
    for f in frames:
        if "creasePattern" in f.classes:
            return f.index
    return 0


def describe_frames(frames: list[ResolvedFrame]) -> list[dict]:
    return [{"index": f.index, "title": f.title, "classes": f.classes} for f in frames]
