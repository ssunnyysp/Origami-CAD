"""Paper-like fold solver (position-based dynamics, vectorized).

Paper can hinge at creases but never stretch, so every mesh edge (pleat
lines, X diagonals, and facet edges alike) is a hard length constraint at its
flat-pattern length. Each substep pulls free vertices a fraction of the way
toward the kinematic wrap target, then repeatedly projects all edge-length
constraints. The sheet therefore collapses around the hub the only way an
inextensible surface can — by pleating at the grid creases and reverse-
folding along the diagonals — instead of stretching like cloth.

Constraint projection is Jacobi-style (all corrections computed against the
same positions, then averaged per vertex), which vectorizes over NumPy;
Gauss-Seidel would be serial Python and the grid mesh is ~30–100× larger
than the old polygonal model. Jacobi converges slower per pass, so the
iteration count is higher than the old solver's 12.

Hub vertices (taxicab radius ≤ HUB_HALF) are pinned: their target is the
flat hub at every foldness, and pinning anchors the wrap.

The solver is warm-started and therefore path-dependent, which is why the
API exposes `solve_sweep` rather than point queries: one monotone 0→1 sweep
at the substep granularity is the canonical fold trajectory, and the client
interpolates between its frames.
"""

from __future__ import annotations

import math

import numpy as np

from .fold_engine import compute_target_positions
from .generator import HUB_CENTER, HUB_HALF, CreasePattern, FlasherParams

TARGET_PULL = 0.3  # fraction of the gap to the kinematic target applied per substep
PROJECT_ITERATIONS = 30  # Jacobi projection passes over all edges per substep
MAX_FOLDNESS_SUBSTEP = 0.02  # large foldness jumps are subdivided for stability
MAX_SUBSTEPS = 80


class FlasherFoldSolver:
    def __init__(self, pattern: CreasePattern, params: FlasherParams):
        self.params = params
        self.flat = np.array([v.position for v in pattern.vertices])  # (V, 2)
        self.pos = compute_target_positions(self.flat, params, 0.0)  # (V, 3)
        self.last_foldness = 0.0

        rho = np.maximum(
            np.abs(self.flat[:, 0] - HUB_CENTER[0]), np.abs(self.flat[:, 1] - HUB_CENTER[1])
        )
        self.free = rho > HUB_HALF + 1e-9  # (V,) pinned hub vertices are immovable

        # Every unique mesh edge is a constraint; the generator's edge list
        # already covers the full triangulation (grid lines + cell X halves).
        self.edge_a = np.array([e.v0 for e in pattern.edges])
        self.edge_b = np.array([e.v1 for e in pattern.edges])
        self.rest = np.linalg.norm(
            self.pos[self.edge_b] - self.pos[self.edge_a], axis=1
        )

        # Per-edge weights: a pinned endpoint takes no correction; its free
        # partner absorbs the full one.
        wa = self.free[self.edge_a].astype(float)
        wb = self.free[self.edge_b].astype(float)
        w_sum = wa + wb
        movable = w_sum > 0
        self.frac_a = np.where(movable, wa / np.where(movable, w_sum, 1.0), 0.0)
        self.frac_b = np.where(movable, wb / np.where(movable, w_sum, 1.0), 0.0)

        # Jacobi averaging: each vertex's correction is the mean over the
        # constraints that touch it.
        counts = np.zeros(len(pattern.vertices))
        np.add.at(counts, self.edge_a, wa)
        np.add.at(counts, self.edge_b, wb)
        self.inv_counts = 1.0 / np.maximum(counts, 1.0)

    def _project(self) -> None:
        delta = self.pos[self.edge_b] - self.pos[self.edge_a]  # (E, 3)
        dist = np.linalg.norm(delta, axis=1)
        dist = np.maximum(dist, 1e-9)
        stretch = (dist - self.rest) / dist  # signed relative error

        corr = np.zeros_like(self.pos)
        np.add.at(corr, self.edge_a, delta * (stretch * self.frac_a)[:, None])
        np.add.at(corr, self.edge_b, -delta * (stretch * self.frac_b)[:, None])
        self.pos += corr * self.inv_counts[:, None]

    def positions_at(self, foldness: float) -> np.ndarray:
        """Advance from the previous foldness to `foldness`; returns (V, 3)."""
        t = min(1.0, max(0.0, foldness))

        if t == 0.0:
            self.pos = compute_target_positions(self.flat, self.params, 0.0)
            self.last_foldness = 0.0
            return self.pos.copy()

        substeps = min(
            MAX_SUBSTEPS,
            max(1, math.ceil(abs(t - self.last_foldness) / MAX_FOLDNESS_SUBSTEP)),
        )
        for s in range(1, substeps + 1):
            step_t = self.last_foldness + (t - self.last_foldness) * s / substeps
            target = compute_target_positions(self.flat, self.params, step_t)

            pull = np.where(self.free, TARGET_PULL, 1.0)[:, None]
            self.pos += (target - self.pos) * pull

            for _ in range(PROJECT_ITERATIONS):
                self._project()

        self.last_foldness = t
        return self.pos.copy()


def solve_sweep(
    pattern: CreasePattern, params: FlasherParams
) -> tuple[list[float], list[list[float]]]:
    """Solve the full fold trajectory once.

    Returns (foldness_samples, frames) where frames[k] holds the xyz triples
    (indexed by vertex id) at foldness_samples[k]. Samples step by
    MAX_FOLDNESS_SUBSTEP so each frame advances the warm-started solver by
    exactly one substep. Coordinates are rounded to 4 decimals — grid units,
    so ~0.1mm on real paper — to keep the JSON payload down.
    """
    solver = FlasherFoldSolver(pattern, params)
    step_count = round(1.0 / MAX_FOLDNESS_SUBSTEP)
    samples = [min(1.0, k * MAX_FOLDNESS_SUBSTEP) for k in range(step_count + 1)]
    frames = [
        np.round(solver.positions_at(t), 4).reshape(-1).tolist() for t in samples
    ]
    return samples, frames
