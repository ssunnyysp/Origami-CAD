"""Constructive tree-fold solver for the square-grid flasher.

The generator's crease pattern is EXACT: folding every crease to its target
dihedral (180° pleats, 90° bends, signed by mountain/valley) closes the
sheet into a 1×1×1 box at machine precision (verified for n=3..17 by a
loop-closure oracle: fold faces along a spanning tree from the hub and check
that every vertex position agrees across all its incident faces).

That exactness enables a much better solver than force-based dynamics:

1. TREE FOLD: pose every face by composing hinge rotations along a BFS
   spanning tree rooted at the hub, with each crease set to a scheduled
   fraction of its target angle. At t=0 (flat) and t=1 (stow) this is
   globally consistent; in between, an intact flasher sheet is NOT a rigid
   mechanism (Lang, J. Mechanisms Robotics 2016), so faces disagree
   slightly where fold loops don't close.
2. RECONCILE: average each vertex across its faces (distributing the loop
   residual), blend with the previous frame for temporal coherence, then
   project all mesh edge lengths back toward their flat values (the sheet
   is inextensible). Residual strain stays in the single digits mid-fold
   (real paper flexes its facets the same way) and well under 1% at the
   endpoints.

SCHEDULE: Lang's fold-angle multipliers say the 180°-class pleat folds
(rings, radials, corner tucks, diagonals) complete much faster than the
90°-class bend folds (the vertical corner bends of the wrap): the sheet
first pleats into a compact star, then the bends curl it around the hub
into the box. Pleats run over t in [0, PLEAT_END], bends over
[BEND_START, 1]; the overlap was chosen by measuring worst-case strain
across the sweep. Fold targets are capped at CAP so the stowed layers stay
visually separated instead of pressing exactly flat.
"""

from __future__ import annotations

from collections import defaultdict, deque

import numpy as np
from scipy.spatial import cKDTree

from .generator import CreasePattern, FlasherParams

STEPS = 60  # foldness samples (frames = STEPS + 1)
PLEAT_END = 0.55  # foldness by which the 180°-class pleats reach full angle
BEND_START = 0.35  # foldness at which the 90°-class bends begin to curl
CAP = 170.0 / 180.0  # fraction of the exact stow angles driven at t=1
PROJECT_ITERS = 200  # edge-length projection sweeps per frame
PROJECT_RELAX = 0.9
PREV_BLEND = 0.5  # weight of the previous frame when seeding the projection
MIN_SEPARATION = 0.10  # closest two flat-far vertices are allowed to get
REPEL_FLAT_EXCLUDE = 1.6  # skip pairs closer than this in the FLAT sheet —
# structurally near pairs (the two sides of a closing pleat) are meant to
# meet; only flat-far pairs approaching in 3-D are real self-intersection.


def _smoothstep(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3.0 - 2.0 * u)


class FlasherFoldSolver:
    def __init__(self, pattern: CreasePattern, params: FlasherParams):
        self.params = params
        by_id = {v.id: v for v in pattern.vertices}
        self.n_out = max(by_id) + 1
        self.flat = np.array([list(by_id[i].position) + [0.0] for i in range(self.n_out)])

        # Signed target angle per edge id: mountains fold +, valleys -,
        # pleats to 180°·fold_factor(=1.0), bends to 90° (fold_factor 0.5).
        self.pleat_target: dict[int, float] = {}
        self.bend_target: dict[int, float] = {}
        for e in pattern.edges:
            if e.assignment in ("facet", "border"):
                continue
            sign = 1.0 if e.assignment == "mountain" else -1.0
            factor = getattr(e, "fold_factor", 1.0)
            target = sign * np.pi * factor
            if factor == 0.5:
                self.bend_target[e.id] = target
            else:
                self.pleat_target[e.id] = target

        # BFS spanning tree over faces from a hub face; each step carries the
        # hinge geometry needed to compose the child's pose from the parent's.
        edges = {e.id: e for e in pattern.edges}
        faces = {f.id: f for f in pattern.faces}
        adj = {a["faceId"]: a["neighbors"] for a in pattern.adjacency}
        hub = next(f.id for f in pattern.faces if f.ring_index == 0)
        seen = {hub}
        self.steps: list[tuple[int, int, int, np.ndarray, np.ndarray, float]] = []
        queue = deque([hub])
        while queue:
            f = queue.popleft()
            for nb in adj[f]:
                g, eid = nb["faceId"], nb["sharedEdgeId"]
                if g in seen:
                    continue
                seen.add(g)
                e = edges[eid]
                p0, p1 = self.flat[e.v0], self.flat[e.v1]
                centroid = np.mean([self.flat[v] for v in faces[g].vertex_ids], axis=0)
                d = p1 - p0
                w = centroid - p0
                side = np.sign(d[0] * w[1] - d[1] * w[0])
                self.steps.append((g, f, eid, p0, d / np.linalg.norm(d), side))
                queue.append(g)
        self.hub = hub
        self.n_faces = len(pattern.faces)
        self.face_vids = np.array([faces[i].vertex_ids for i in range(self.n_faces)])

        # All triangle edges (creases + facet halves) for inextensibility.
        edge_set = set()
        for f in pattern.faces:
            t = f.vertex_ids
            for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                edge_set.add((min(a, b), max(a, b)))
        self.ea = np.array([a for a, _ in sorted(edge_set)])
        self.eb = np.array([b for _, b in sorted(edge_set)])
        self.rest = np.linalg.norm(self.flat[self.eb] - self.flat[self.ea], axis=1)
        deg = np.zeros(self.n_out)
        np.add.at(deg, self.ea, 1.0)
        np.add.at(deg, self.eb, 1.0)
        self.inv_deg = 1.0 / np.maximum(deg, 1.0)

    def _tree_positions(self, angle_by_edge: dict[int, float]) -> np.ndarray:
        R = np.zeros((self.n_faces, 3, 3))
        t = np.zeros((self.n_faces, 3))
        R[self.hub] = np.eye(3)
        for g, f, eid, p0, d, side in self.steps:
            phi = angle_by_edge.get(eid, 0.0)
            if phi != 0.0:
                a = -side * phi
                c, s = np.cos(a), np.sin(a)
                K = np.array([[0, -d[2], d[1]], [d[2], 0, -d[0]], [-d[1], d[0], 0]])
                Rl = np.eye(3) + s * K + (1 - c) * (K @ K)
                tl = p0 - Rl @ p0
            else:
                Rl, tl = np.eye(3), np.zeros(3)
            R[g] = R[f] @ Rl
            t[g] = R[f] @ tl + t[f]
        pts = np.einsum("fij,fvj->fvi", R, self.flat[self.face_vids]) + t[:, None, :]
        ids = self.face_vids.reshape(-1)
        acc = np.zeros((self.n_out, 3))
        cnt = np.zeros(self.n_out)
        np.add.at(acc, ids, pts.reshape(-1, 3))
        np.add.at(cnt, ids, 1.0)
        return acc / np.maximum(cnt, 1.0)[:, None]

    def _project_lengths(self, X: np.ndarray, iters: int = PROJECT_ITERS) -> np.ndarray:
        for _ in range(iters):
            d = X[self.eb] - X[self.ea]
            L = np.linalg.norm(d, axis=1, keepdims=True)
            corr = (L - self.rest[:, None]) * (d / np.maximum(L, 1e-9)) * PROJECT_RELAX
            dX = np.zeros_like(X)
            np.add.at(dX, self.ea, corr)
            np.add.at(dX, self.eb, -corr)
            X = X + dX * self.inv_deg[:, None]
        return X

    def _repel(self, X: np.ndarray) -> np.ndarray:
        """Push apart vertex pairs that are close in 3-D but far apart in the
        flat sheet — genuine self-intersection, not two sides of a pleat
        meeting as intended."""
        pairs = cKDTree(X).query_pairs(MIN_SEPARATION, output_type="ndarray")
        if len(pairs) == 0:
            return X
        i, j = pairs[:, 0], pairs[:, 1]
        flat_d = np.linalg.norm(self.flat[i, :2] - self.flat[j, :2], axis=1)
        far = flat_d > REPEL_FLAT_EXCLUDE
        i, j = i[far], j[far]
        if len(i) == 0:
            return X
        d = X[j] - X[i]
        dist = np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-6)
        push = (MIN_SEPARATION - dist[:, 0]).clip(min=0.0)[:, None] * (d / dist) * 0.5
        F = np.zeros_like(X)
        np.add.at(F, i, -push)
        np.add.at(F, j, push)
        return X + F

    def solve_sweep(self):
        frames = []
        samples = []
        X_prev: np.ndarray | None = None
        for s in range(STEPS + 1):
            t = s / STEPS
            fp = _smoothstep(t / PLEAT_END) * CAP
            fb = _smoothstep((t - BEND_START) / (1.0 - BEND_START)) * CAP
            ang = {eid: v * fp for eid, v in self.pleat_target.items()}
            ang.update({eid: v * fb for eid, v in self.bend_target.items()})
            X = self._tree_positions(ang)
            if X_prev is not None:
                X = PREV_BLEND * X_prev + (1.0 - PREV_BLEND) * X
            X = self._project_lengths(X)
            # Separate genuinely self-intersecting layers, then lightly
            # re-project so the separation doesn't show up as stretch.
            X = self._repel(X)
            X = self._project_lengths(X, iters=30)
            X_prev = X
            frames.append(np.round(X, 4).reshape(-1).tolist())
            samples.append(t)
        return samples, frames


def solve_sweep(pattern: CreasePattern, params: FlasherParams):
    return FlasherFoldSolver(pattern, params).solve_sweep()
