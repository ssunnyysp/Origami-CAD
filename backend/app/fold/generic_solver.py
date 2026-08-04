"""Best-effort fold solver for arbitrary imported crease patterns.

This is a deliberate, self-contained adaptation of the same crease-angle-
driven approach as `app.flasher.solver` (dihedral-bend toward a mountain/
valley target angle, hard edge-length projection for inextensibility,
non-adjacent-vertex repulsion against self-intersection) — see that module's
docstring for why the algorithm looks the way it does. It is copied here
rather than imported/refactored for two reasons: `solver.py` is being
actively rewritten on a concurrent branch (fix/origami-flasher-geometry), and
its pin/seed selection is inherently flasher-specific (a known central hub
cell, ring index for symmetry-breaking) whereas an arbitrary imported FOLD
pattern has neither. Once that branch merges, this and `solver.py` sharing a
common base is worth revisiting — see the FOLD PR description.

Generalizations relative to solver.py:
- Pin selection: the flasher pins the known hub square; here we pin the
  largest-area face instead, an arbitrary but reasonable anchor for a pattern
  with no designated center.
- Symmetry-breaking seed: the flasher alternates by ring index; here we
  alternate by BFS hop-distance (over face adjacency) from the anchor face,
  which is the generic analogue for a pattern with no ring structure.
- MAX_ANGLE is capped more conservatively (110°) than the flasher's tuned
  130°, since this runs on topology this code has never been validated
  against: pushing the target angle too far causes local crumpling instead
  of a uniform fold.
"""

from __future__ import annotations

from collections import defaultdict, deque

import numpy as np
from scipy.spatial import cKDTree

from ..flasher.generator import CreasePattern

MAX_ANGLE = np.radians(110.0)
BEND = 3.0
SEED = 0.05
DT = 0.05
DAMP = 0.9
LENGTH_ITERS = 10
LENGTH_RELAX = 0.9
MIN_SEPARATION = 0.12
REPEL_GAIN = 1.2
REPEL_FLAT_EXCLUDE = 1.6
STEPS = 60
SUBSTEPS = 45


def _cross2(ax, ay, bx, by):
    return ax * by - ay * bx


def _anchor_face(pattern: CreasePattern) -> int:
    """The largest-area face — an arbitrary but reasonable "hub" to pin for a
    pattern with no designated center."""
    by_id = {v.id: v for v in pattern.vertices}
    best_id, best_area = 0, -1.0
    for f in pattern.faces:
        pts = [by_id[v].position for v in f.vertex_ids]
        area = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            area += x1 * y2 - x2 * y1
        area = abs(area) / 2
        if area > best_area:
            best_area, best_id = area, f.id
    return best_id


class GenericFoldSolver:
    def __init__(self, pattern: CreasePattern):
        by_id = {v.id: v for v in pattern.vertices}
        order = sorted(by_id)
        self.n_out = max(order) + 1
        self.flat = np.array([list(by_id[i].position) + [0.0] for i in order])
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
            hi.append(a)
            hj.append(b)
            hk.append(k)
            hl.append(l)
            sgn.append({"mountain": 1.0, "valley": -1.0}.get(asg, 0.0))
        self.hi, self.hj, self.hk, self.hl = (np.array(a, dtype=int) for a in (hi, hj, hk, hl))
        self.sgn = np.array(sgn)

        self.ea = np.array([a for a, _ in edge_tris], dtype=int)
        self.eb = np.array([b for _, b in edge_tris], dtype=int)
        self.rest = (
            np.linalg.norm(self.flat[self.eb] - self.flat[self.ea], axis=1) if len(self.ea) else np.array([])
        )
        deg = np.zeros(V)
        if len(self.ea):
            np.add.at(deg, self.ea, 1.0)
            np.add.at(deg, self.eb, 1.0)
        self.inv_deg = 1.0 / np.maximum(deg, 1.0)

        pinned = np.zeros(V, dtype=bool)
        depth = np.zeros(V)
        if pattern.faces:
            anchor = _anchor_face(pattern)
            for v in pattern.faces[anchor].vertex_ids:
                pinned[v] = True

            faces_by_edge: dict[int, list[int]] = defaultdict(list)
            for f in pattern.faces:
                for e in f.edge_ids:
                    faces_by_edge[e].append(f.id)
            face_adj: dict[int, list[int]] = defaultdict(list)
            for e, fids in faces_by_edge.items():
                if len(fids) == 2:
                    face_adj[fids[0]].append(fids[1])
                    face_adj[fids[1]].append(fids[0])
            face_depth = {anchor: 0}
            q = deque([anchor])
            while q:
                cur = q.popleft()
                for nb in face_adj[cur]:
                    if nb not in face_depth:
                        face_depth[nb] = face_depth[cur] + 1
                        q.append(nb)
            for f in pattern.faces:
                d = face_depth.get(f.id, 0)
                for v in f.vertex_ids:
                    depth[v] = d
        self.pinned = pinned
        self.depth = depth

    def _repel(self, X: np.ndarray) -> None:
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
        if len(self.ea) == 0:
            return
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
        X[:, 2] = SEED * np.where(self.depth % 2 == 0, 1.0, -1.0) * np.hypot(X[:, 0], X[:, 1])
        X[self.pinned, 2] = 0.0
        vel = np.zeros_like(X)
        frames = [np.round(self.flat, 4).reshape(-1).tolist()]
        samples = [0.0]
        for s in range(1, STEPS + 1):
            t = s / STEPS
            for _ in range(SUBSTEPS):
                F = np.zeros_like(X)
                if len(self.hi):
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


def solve_sweep_generic(pattern: CreasePattern):
    return GenericFoldSolver(pattern).solve_sweep()
