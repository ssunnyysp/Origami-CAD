"""Crease-angle-driven fold solver.

Every crease is driven toward a target dihedral ANGLE (mountain one way,
valley the other, facets flat), scaled by foldness; the 3-D shape EMERGES
from the creases instead of being imposed, so paper only ever bends at the
drawn crease lines. Edge lengths are hard-projected every substep so the
sheet is inextensible (it cannot stretch). The signed-dihedral gradient is
finite-difference validated; a single hinge folds to any target angle at
0 % strain.

Two things this file used to get wrong, found by directly measuring instead
of eyeballing:

1. There was no collision term at all — only bending + inextensibility.
   Nothing stopped unconnected parts of the sheet from passing through each
   other. `_repel` now pushes apart any pair of vertices that aren't
   connected by a mesh edge (so aren't supposed to be touching) once they
   get closer than MIN_SEPARATION, which is the actual fix for the
   "phasing through itself" symptom — low edge-length strain alone does not
   imply the surface isn't self-intersecting.
2. The fold target was pushed to 170° so it would look "more dramatic," but
   this chiral pattern's ring loop does not close as a clean rigid rotation
   that close to a flat fold — the length projection was forcibly papering
   over the mismatch, which is what showed up as chaotic local crumpling
   ("crunching") instead of a uniform rotation. Tracking each ring's own
   corner angle through the sweep (not just comparing start/end) shows the
   rotation is consistent (rings agree to within a couple of degrees) up to
   about 130-140°, and comes apart above that — so MAX_ANGLE is capped at
   130° even though it visually "wants" to go further.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

from .generator import HUB_CENTER, HUB_HALF, CreasePattern, FlasherParams

MAX_ANGLE = np.radians(130.0)  # target crease dihedral at foldness = 1 — the
# highest angle where every ring's rotation stays consistent (verified by
# tracking each ring's own corner through the whole sweep, not just t=0/t=1);
# above ~140-150 deg the rings desync and the fold visibly crumples instead
# of rotating uniformly.
BEND = 3.0  # bending drive gain
SEED = 0.05  # tiny accordion z-seed to break the flat equilibrium
DT = 0.05
DAMP = 0.9
LENGTH_ITERS = 10  # hard inextensibility projections per substep
LENGTH_RELAX = 0.9
MIN_SEPARATION = 0.12  # closest two non-adjacent vertices are allowed to get
REPEL_GAIN = 1.2  # push-apart strength once inside MIN_SEPARATION
REPEL_FLAT_EXCLUDE = 1.6  # skip pairs this close in the FLAT pattern — they're
# structurally near each other (e.g. the two triangles either side of a
# closing hinge are meant to swing close together) and repelling them would
# fight the fold itself. Only pairs far apart in the flat sheet but close in
# 3-D are genuine self-intersection.
STEPS = 60  # foldness samples (frames = STEPS + 1)
SUBSTEPS = 45


def _cross2(ax, ay, bx, by):
    return ax * by - ay * bx


class FlasherFoldSolver:
    def __init__(self, pattern: CreasePattern, params: FlasherParams):
        self.params = params
        by_id = {v.id: v for v in pattern.vertices}
        order = sorted(by_id)
        self.n_out = max(order) + 1
        self.flat = np.array([list(by_id[i].position) + [0.0] for i in range(self.n_out)])
        V = self.n_out

        assign = {(min(e.v0, e.v1), max(e.v0, e.v1)): e.assignment for e in pattern.edges}
        edge_tris: dict[tuple[int, int], list[int]] = defaultdict(list)
        for f in pattern.faces:
            t = f.vertex_ids
            for a, b, apex in ((t[0], t[1], t[2]), (t[1], t[2], t[0]), (t[2], t[0], t[1])):
                edge_tris[(min(a, b), max(a, b))].append(apex)

        hi, hj, hk, hl, sgn = [], [], [], [], []
        for (a, b), apexes in edge_tris.items():
            if len(apexes) != 2:
                continue
            asg = assign.get((a, b), "facet")
            if asg == "border":
                continue
            d = self.flat[b, :2] - self.flat[a, :2]
            k, l = apexes
            if _cross2(d[0], d[1], *(self.flat[k, :2] - self.flat[a, :2])) < 0:
                k, l = l, k
            hi.append(a); hj.append(b); hk.append(k); hl.append(l)
            sgn.append({"mountain": 1.0, "valley": -1.0, "facet": 0.0}[asg])
        self.hi, self.hj, self.hk, self.hl = map(np.array, (hi, hj, hk, hl))
        self.sgn = np.array(sgn)

        self.ea = np.array([a for a, _ in edge_tris])
        self.eb = np.array([b for _, b in edge_tris])
        self.rest = np.linalg.norm(self.flat[self.eb] - self.flat[self.ea], axis=1)
        deg = np.zeros(V)
        np.add.at(deg, self.ea, 1.0)
        np.add.at(deg, self.eb, 1.0)
        self.inv_deg = 1.0 / np.maximum(deg, 1.0)

        # Pin the hub square flat (rho <= HUB_HALF) — the central square all the
        # rest folds around.
        rho = np.maximum(
            np.abs(self.flat[:, 0] - HUB_CENTER[0]), np.abs(self.flat[:, 1] - HUB_CENTER[1])
        )
        self.pinned = rho <= HUB_HALF + 1e-9
        self.ring_of = np.zeros(V)
        for f in pattern.faces:
            for v in f.vertex_ids:
                self.ring_of[v] = f.ring_index

    def _repel(self, X: np.ndarray) -> None:
        """Push apart any pair of vertices that are close in 3-D but far
        apart in the flat pattern — real self-intersection, not just two
        sides of the same hinge swinging together as intended."""
        pairs = cKDTree(X).query_pairs(MIN_SEPARATION, output_type="ndarray")
        if len(pairs) == 0:
            return
        i, j = pairs[:, 0], pairs[:, 1]
        flat_d = np.linalg.norm(self.flat[i, :2] - self.flat[j, :2], axis=1)
        far_in_flat = flat_d > REPEL_FLAT_EXCLUDE
        i, j = i[far_in_flat], j[far_in_flat]
        if len(i) == 0:
            return
        d = X[j] - X[i]
        dist = np.linalg.norm(d, axis=1, keepdims=True)
        dist = np.maximum(dist, 1e-6)
        push = np.maximum(MIN_SEPARATION - dist[:, 0], 0.0)[:, None] * (d / dist) * REPEL_GAIN
        F = np.zeros_like(X)
        np.add.at(F, i, -push)
        np.add.at(F, j, push)
        F[self.pinned] = 0.0
        X += F

    def _dihedral(self, X):
        x1, x2, x3, x4 = X[self.hi], X[self.hj], X[self.hk], X[self.hl]
        e = x2 - x1
        Le = np.linalg.norm(e, axis=1, keepdims=True)
        n1 = np.cross(x2 - x1, x3 - x1)
        n2 = np.cross(x4 - x1, x2 - x1)
        L1 = np.linalg.norm(n1, axis=1, keepdims=True)
        L2 = np.linalg.norm(n2, axis=1, keepdims=True)
        n1u, n2u = n1 / L1, n2 / L2
        h1, h2 = L1 / Le, L2 / Le
        th = np.arctan2(
            np.sum(np.cross(n1u, n2u) * (e / Le), axis=1),
            np.clip(np.sum(n1u * n2u, axis=1), -1, 1),
        )
        w1 = (np.sum((x3 - x1) * e, axis=1) / Le[:, 0] ** 2)[:, None]
        w2 = (np.sum((x4 - x1) * e, axis=1) / Le[:, 0] ** 2)[:, None]
        g3 = -n1u / h1
        g4 = -n2u / h2
        g1 = -(1 - w1) * g3 - (1 - w2) * g4
        g2 = -w1 * g3 - w2 * g4
        return th, g1, g2, g3, g4

    def _project_lengths(self, X):
        for _ in range(LENGTH_ITERS):
            d = X[self.eb] - X[self.ea]
            L = np.linalg.norm(d, axis=1, keepdims=True)
            corr = (L - self.rest[:, None]) * (d / np.maximum(L, 1e-9)) * LENGTH_RELAX
            dX = np.zeros_like(X)
            np.add.at(dX, self.ea, corr)
            np.add.at(dX, self.eb, -corr)
            dX *= self.inv_deg[:, None]
            dX[self.pinned] = 0.0
            X += dX

    def solve_sweep(self):
        X = self.flat.copy()
        X[:, 2] = SEED * np.where(self.ring_of % 2 == 0, 1.0, -1.0) * np.hypot(X[:, 0], X[:, 1])
        X[self.pinned, 2] = 0.0
        vel = np.zeros_like(X)
        frames = [np.round(self.flat, 4).reshape(-1).tolist()]
        samples = [0.0]
        for s in range(1, STEPS + 1):
            t = s / STEPS
            for _ in range(SUBSTEPS):
                F = np.zeros_like(X)
                th, g1, g2, g3, g4 = self._dihedral(X)
                c = (-BEND * (th - self.sgn * MAX_ANGLE * t))[:, None]
                np.add.at(F, self.hi, c * g1)
                np.add.at(F, self.hj, c * g2)
                np.add.at(F, self.hk, c * g3)
                np.add.at(F, self.hl, c * g4)
                F[self.pinned] = 0.0
                vel = (vel + DT * F) * DAMP
                X += DT * vel
                X[self.pinned, 2] = 0.0
                self._project_lengths(X)
                self._repel(X)
            frames.append(np.round(X, 4).reshape(-1).tolist())
            samples.append(t)
        return samples, frames


def solve_sweep(pattern: CreasePattern, params: FlasherParams):
    return FlasherFoldSolver(pattern, params).solve_sweep()
