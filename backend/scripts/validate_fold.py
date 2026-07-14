"""Standing validation harness for FOLD import/export — no server needed.
Run with:

    cd backend
    PYTHONPATH="$PWD" .venv/bin/python scripts/validate_fold.py

There's no test suite in this repo (see CLAUDE.md); this follows the same
"ad-hoc script measuring real behavior" convention as the flasher generator's
own validation, checking three things a unit test would but a screenshot
can't:

1. Round-trip: generate a flasher, export it to FOLD, re-import it, and
   confirm the reconstructed pattern is exactly equivalent (not just
   "close") — same vertex positions, same edge assignments, same faces.
2. Real-world files: every .fold file in tests_data/ (downloaded from
   github.com/edemaine/fold's own examples/ directory) imports without
   raising, whether it's a flat crease pattern (animated by the generic
   solver) or an already-folded 3-D pose (shown statically).
3. Malformed input fails with FoldValidationError and a specific message,
   never an unhandled exception.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.flasher.generator import FlasherParams, generate_flasher  # noqa: E402
from app.flasher.solver import solve_sweep  # noqa: E402
from app.fold.errors import FoldValidationError  # noqa: E402
from app.fold.exporter import build_fold_document  # noqa: E402
from app.fold.importer import import_fold_document  # noqa: E402
from app.schemas import CreasePatternOut  # noqa: E402

TESTS_DATA = Path(__file__).resolve().parent.parent / "tests_data"

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if condition:
        print(f"  OK   {message}")
    else:
        print(f"  FAIL {message}")
        failures.append(message)


def round_trip_test() -> None:
    print("\n=== round-trip: generate -> export -> re-import ===")
    params = FlasherParams(grid_divisions=7, layer_gap_ratio=0.14, height_ratio=0.9)
    pattern = generate_flasher(params)
    samples, frames = solve_sweep(pattern, params)
    pattern_out = CreasePatternOut.from_pattern(pattern)

    doc = build_fold_document(pattern_out, frames[-1], "Round-trip flasher")

    # Frame 0 (the flat crease pattern) must reconstruct the generated pattern exactly.
    result = import_fold_document(doc, frame_index=0)
    check(len(result.warnings) == 0, f"no warnings re-importing the flat frame (got {result.warnings})")

    orig_v = {v.id: v.position for v in pattern.vertices}
    new_v = {v.id: v.position for v in result.pattern.vertices}
    check(set(orig_v) == set(new_v), "same vertex id set")
    max_err = max((abs(orig_v[i][0] - new_v[i][0]) + abs(orig_v[i][1] - new_v[i][1]) for i in orig_v), default=0)
    check(max_err < 1e-9, f"vertex positions match exactly (max error {max_err})")

    orig_e = sorted((min(e.v0, e.v1), max(e.v0, e.v1), e.assignment) for e in pattern.edges)
    new_e = sorted((min(e.v0, e.v1), max(e.v0, e.v1), e.assignment) for e in result.pattern.edges)
    check(orig_e == new_e, f"edge assignments match ({len(orig_e)} edges)")

    orig_f = sorted(tuple(sorted(f.vertex_ids)) for f in pattern.faces)
    new_f = sorted(tuple(sorted(f.vertex_ids)) for f in result.pattern.faces)
    check(orig_f == new_f, f"face vertex sets match ({len(orig_f)} faces)")

    # Frame 1 (the folded state) should come back as a static two-frame pose,
    # not an invented animation, and should carry a clear warning saying so.
    folded_result = import_fold_document(doc, frame_index=1)
    check(len(folded_result.frames) == 2, "folded-state frame imports as a static 2-frame pose")
    check(len(folded_result.warnings) == 1, "folded-state import carries exactly one explanatory warning")


def sample_file_test() -> None:
    print("\n=== real-world sample files (tests_data/*.fold) ===")
    fold_files = sorted(TESTS_DATA.glob("*.fold"))
    check(len(fold_files) > 0, "sample .fold files are present")
    for path in fold_files:
        with open(path) as f:
            doc = json.load(f)
        try:
            result = import_fold_document(doc, None)
            print(
                f"  OK   {path.name}: {len(result.pattern.vertices)}v "
                f"{len(result.pattern.edges)}e {len(result.pattern.faces)}f, "
                f"{len(result.frames)} frame(s), warnings={result.warnings}"
            )
        except Exception as err:  # noqa: BLE001 — this IS the check: nothing should raise
            print(f"  FAIL {path.name}: raised {type(err).__name__}: {err}")
            failures.append(f"{path.name} raised {type(err).__name__}")


def malformed_input_test() -> None:
    print("\n=== malformed input fails gracefully ===")
    cases = [
        ({"file_spec": 1}, "missing vertices_coords"),
        ({"vertices_coords": [[0, 0], [1, 0]], "edges_vertices": [[0, 5]]}, "out-of-range edge vertex"),
        (
            {
                "vertices_coords": [[0, 0], [1, 0], [1, 1]],
                "edges_vertices": [[0, 1], [1, 2]],
                "edges_assignment": ["M"],
            },
            "mismatched edges_assignment length",
        ),
        ("not a dict", "wrong top-level JSON type"),
        (
            {
                "vertices_coords": [[0, 0], [1, 0], [1, 1]],
                "edges_vertices": [[0, 1], [1, 2], [2, 0]],
                "faces_vertices": [[0, 1]],
            },
            "face with fewer than 3 vertices",
        ),
    ]
    for doc, description in cases:
        try:
            import_fold_document(doc, None)
            check(False, f"raises FoldValidationError for: {description}")
        except FoldValidationError as err:
            check(True, f"raises FoldValidationError for: {description} ({err})")
        except Exception as err:  # noqa: BLE001
            check(False, f"raises FoldValidationError (not {type(err).__name__}) for: {description}")


if __name__ == "__main__":
    round_trip_test()
    sample_file_test()
    malformed_input_test()

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("all checks passed")
