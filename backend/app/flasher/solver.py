"""Paper-like fold solver (position-based dynamics).

Port of the original frontend foldSolver.ts: paper can hinge at creases but
never stretch, so every rendered triangle edge is a hard length constraint at
its flat-pattern length. Each solve step pulls free vertices a fraction of
the way toward the kinematic wrap target, then repeatedly projects all
edge-length constraints (Gauss-Seidel). The sheet therefore coils around the
hub the only way an inextensible surface can — by folding into itself and
buckling at creases — instead of stretching like sheet metal.

Hub (ring 0) vertices are pinned: their target is the flat hub at every
foldness, and pinning anchors the wrap.

The solver is warm-started and therefore path-dependent, which is why the API
exposes `solve_sweep` rather than point queries: one monotone 0→1 sweep at
the substep granularity is the canonical fold trajectory, and the client
interpolates between its frames.
"""

from __future__ import annotations

import math

from .fold_engine import compute_target_positions
from .generator import CreasePattern, FlasherParams

TARGET_PULL = 0.3  # fraction of the gap to the kinematic target applied per substep
PROJECT_ITERATIONS = 12  # Gauss-Seidel passes over all edges per substep
MAX_FOLDNESS_SUBSTEP = 0.02  # large foldness jumps are subdivided for stability
MAX_SUBSTEPS = 80


class FlasherFoldSolver:
    def __init__(self, pattern: CreasePattern, params: FlasherParams):
        self.params = params
        self.pinned_count = params.sides  # ring-0 vertex ids are [0, pinned_count)
        self.pos = compute_target_positions(params, 0.0)
        self.last_foldness = 0.0

        # Constraints come from the RENDERED triangles (faces fan-triangulated
        # from their first vertex), so the constrained surface is exactly the
        # surface drawn on screen — including the central polygon's fan
        # diagonals, which aren't pattern edges.
        self.constraints: list[tuple[int, int, float]] = []  # (a, b, rest_length)
        seen: set[tuple[int, int]] = set()

        def add_constraint(a: int, b: int) -> None:
            key = (a, b) if a < b else (b, a)
            if key in seen:
                return
            seen.add(key)
            ka, kb = a * 3, b * 3
            rest = math.hypot(
                self.pos[ka] - self.pos[kb],
                self.pos[ka + 1] - self.pos[kb + 1],
                self.pos[ka + 2] - self.pos[kb + 2],
            )
            self.constraints.append((a, b, rest))

        for face in pattern.faces:
            ids = face.vertex_ids
            for i in range(1, len(ids) - 1):
                add_constraint(ids[0], ids[i])
                add_constraint(ids[i], ids[i + 1])
                add_constraint(ids[0], ids[i + 1])

    def positions_at(self, foldness: float) -> list[float]:
        """Advance from the previous foldness to `foldness`; returns xyz triples."""
        t = min(1.0, max(0.0, foldness))

        if t == 0.0:
            self.pos = compute_target_positions(self.params, 0.0)
            self.last_foldness = 0.0
            return list(self.pos)

        substeps = min(
            MAX_SUBSTEPS,
            max(1, math.ceil(abs(t - self.last_foldness) / MAX_FOLDNESS_SUBSTEP)),
        )
        pos = self.pos
        for s in range(1, substeps + 1):
            step_t = self.last_foldness + (t - self.last_foldness) * s / substeps
            target = compute_target_positions(self.params, step_t)

            for v in range(len(pos) // 3):
                k = v * 3
                pull = 1.0 if v < self.pinned_count else TARGET_PULL
                pos[k] += (target[k] - pos[k]) * pull
                pos[k + 1] += (target[k + 1] - pos[k + 1]) * pull
                pos[k + 2] += (target[k + 2] - pos[k + 2]) * pull

            for _ in range(PROJECT_ITERATIONS):
                for a, b, rest in self.constraints:
                    ka, kb = a * 3, b * 3
                    dx = pos[kb] - pos[ka]
                    dy = pos[kb + 1] - pos[ka + 1]
                    dz = pos[kb + 2] - pos[ka + 2]
                    dist = math.hypot(dx, dy, dz)
                    if dist < 1e-9:
                        continue

                    wa = 0 if a < self.pinned_count else 1
                    wb = 0 if b < self.pinned_count else 1
                    w_sum = wa + wb
                    if w_sum == 0:
                        continue

                    scale = (dist - rest) / dist / w_sum
                    pos[ka] += dx * scale * wa
                    pos[ka + 1] += dy * scale * wa
                    pos[ka + 2] += dz * scale * wa
                    pos[kb] -= dx * scale * wb
                    pos[kb + 1] -= dy * scale * wb
                    pos[kb + 2] -= dz * scale * wb

        self.last_foldness = t
        return list(self.pos)


def solve_sweep(
    pattern: CreasePattern, params: FlasherParams
) -> tuple[list[float], list[list[float]]]:
    """Solve the full fold trajectory once.

    Returns (foldness_samples, frames) where frames[k] holds the xyz triples
    at foldness_samples[k]. Samples step by MAX_FOLDNESS_SUBSTEP so each frame
    advances the warm-started solver by exactly one substep — the same
    trajectory the interactive frontend solver used to trace.
    """
    solver = FlasherFoldSolver(pattern, params)
    step_count = round(1.0 / MAX_FOLDNESS_SUBSTEP)
    samples = [min(1.0, k * MAX_FOLDNESS_SUBSTEP) for k in range(step_count + 1)]
    frames = [solver.positions_at(t) for t in samples]
    return samples, frames
