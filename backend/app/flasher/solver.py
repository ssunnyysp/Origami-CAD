"""Single-DOF fold solver: a rigid forward-kinematics PREDICTOR, refined by a
short, deterministic dihedral-angle relaxation.

## Why not pure forward kinematics

A flasher vertex where 4 creases meet (2 circumferential + 2 spokes) is
flat-foldable — Maekawa's condition (mountain-count minus valley-count = ±2)
holds at every interior vertex of this pattern by construction (see
`generator.py`'s `spoke_gender`/`ring_gender` docstrings) — but flat-foldable
does not mean "every incident crease bends by the same magnitude at every
foldness." The exact relationship between a degree-4 vertex's 4 fold angles
as a single DOF sweeps is a nonlinear spherical-linkage equation, not a
shared linear schedule. Driving every crease by
`angle(t) = sign * MAX_BEND * t` and taking that as the literal 3-D pose
(implemented first; see PR description) is only correct to FIRST ORDER in
t — measured strain grows from ~0% at t=0.02 to 120%+ by t=1, which confirms
the pattern really is a valid infinitesimal mechanism (the naive schedule is
at least locally consistent, so the crease pattern itself is sound) but the
exact nonlinear per-vertex relationship needs solving, not assuming.

Solving that exactly for a general m-ring, n-sided pattern means a coupled
spherical-linkage system across every interior vertex simultaneously — a
harder problem than fits this pass (see `docs/FLASHER_NOTES.md` Phase 3).
Rather than guess a second closed form blindly, this solver keeps the rigid
FK prediction (still driven by the same single shared `angle(t)` schedule —
the actual single-DOF requirement) as a qualitatively-correct SEED, then
refines it with a short dihedral-angle relaxation using the same
bend-toward-target + inextensibility-projection + collision machinery as the
project's earlier solver — but seeded from the correct rigid shape instead
of a small random perturbation of the flat sheet, so it converges in far
fewer substeps, to a far smaller residual, and with no random seed (so it is
exactly reproducible run to run, unlike a relaxation started from noise).

Every fold target is still one shared function of `foldness` alone,
`sign * MAX_BEND * t`; the relaxation only resolves the fact that this
shared schedule doesn't exactly satisfy every vertex's nonlinear closure
simultaneously. `scripts/validate_flasher.py` measures the residual strain
this leaves; see the PR description for the measurement sweep that picked
`MAX_BEND`.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

from .generator import CreasePattern, FlasherParams

MAX_BEND = np.radians(120.0)  # target crease bend at foldness = 1, shared by
# every real crease. Measured by sweeping 90-150 deg: strain is NOT
# monotonic in this angle (it depends on how far the FK seed drifts from the
# true nonlinear closure, which oscillates with angle), so this was picked
# empirically, not assumed — see PR description for the sweep table.
STEPS = 60  # foldness samples (frames = STEPS + 1)
BEND = 5.0  # bending drive gain toward the target dihedral
DT = 0.06
DAMP = 0.85
SUBSTEPS = 80  # measured: the naive shared-angle-schedule seed leaves more
# residual error to relax out than the project's earlier (topologically
# simpler, square-grid) solver needed, especially as ring count grows —
# see PR description, "known limitation: ring count vs. residual strain."
LENGTH_ITERS = 20
LENGTH_RELAX = 0.9
MIN_SEPARATION = 0.12
REPEL_GAIN = 1.2
REPEL_FLAT_EXCLUDE = 1.6  # flat-pattern distance below which two vertices are
# structurally near each other (e.g. either side of a closing hinge) and are
# expected to swing close together — only pairs far apart in the flat sheet
# but close in 3-D are genuine self-intersection.


def _rotation_matrix(axis: np.ndarray, angle: float) -> np.ndarray:
    """Rodrigues' rotation formula: 3x3 rotation by `angle` about unit `axis`."""
    x, y, z = axis
    K = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)


def _cross2(ax, ay, bx, by):
    return ax * by - ay * bx


def _face_triangles(vertex_ids: list[int]):
    """Fan-triangulate a (possibly non-triangular, but always convex and flat
    in the rest pattern) face for hinge-apex lookup. A no-op for triangles.
    Only the hub face has more than 3 vertices, and it is rigid/pinned, so
    which fan diagonal is used never matters — it's never a real crease."""
    for k in range(1, len(vertex_ids) - 1):
        yield (vertex_ids[0], vertex_ids[k], vertex_ids[k + 1])


class FlasherFoldSolver:
    def __init__(self, pattern: CreasePattern, params: FlasherParams):
        self.pattern = pattern
        by_id = {v.id: v for v in pattern.vertices}
        order = sorted(by_id)
        self.n_out = max(order) + 1
        self.flat = np.array([list(by_id[i].position) + [0.0] for i in range(self.n_out)])
        V = self.n_out

        assign = {e.id: e.assignment for e in pattern.edges}
        edge_endpoints = {e.id: (e.v0, e.v1) for e in pattern.edges}

        # --- FK predictor: spanning tree over face adjacency, rooted at the
        # hub (face 0, always emitted first by generator.py). -------------------
        adjacency = {a["faceId"]: a["neighbors"] for a in pattern.adjacency}
        root = 0
        parent: dict[int, tuple[int, int]] = {}
        order_bfs: list[int] = [root]
        visited = {root}
        head = 0
        while head < len(order_bfs):
            face_id = order_bfs[head]
            head += 1
            for nb in adjacency.get(face_id, []):
                nf = nb["faceId"]
                if nf in visited:
                    continue
                visited.add(nf)
                parent[nf] = (face_id, nb["sharedEdgeId"])
                order_bfs.append(nf)
        missing = {f.id for f in pattern.faces} - visited
        if missing:
            raise RuntimeError(f"face-adjacency graph is disconnected: faces {missing} unreached")
        self.bfs_order = order_bfs
        self.parent = parent

        self.hinge_v0: dict[int, int] = {}
        self.hinge_v1: dict[int, int] = {}
        self.hinge_sign: dict[int, float] = {}
        for child, (_, edge_id) in parent.items():
            v0, v1 = edge_endpoints[edge_id]
            self.hinge_v0[child] = v0
            self.hinge_v1[child] = v1
            self.hinge_sign[child] = {"mountain": 1.0, "valley": -1.0, "facet": 0.0}[assign[edge_id]]
        self.face_vertex_ids = [f.vertex_ids for f in pattern.faces]

        # --- dihedral-angle relaxation setup (fan-triangulated hinge table,
        # same construction the project's earlier solver used). -----------------
        edge_tris: dict[tuple[int, int], list[int]] = defaultdict(list)
        for f in pattern.faces:
            for a, b, apex in _face_triangles(f.vertex_ids):
                edge_tris[(min(a, b), max(a, b))].append(apex)
                a2, b2, apex2 = b, apex, a
                edge_tris[(min(a2, b2), max(a2, b2))].append(apex2)
                a3, b3, apex3 = apex, a, b
                edge_tris[(min(a3, b3), max(a3, b3))].append(apex3)

        hi, hj, hk, hl, sgn = [], [], [], [], []
        for (a, b), apexes in edge_tris.items():
            if len(apexes) != 2:
                continue
            asg = assign.get((a, b), "facet")
            if asg == "border":
                continue
            d = self.flat[b, :2] - self.flat[a, :2]
            k_apex, l_apex = apexes
            if _cross2(d[0], d[1], *(self.flat[k_apex, :2] - self.flat[a, :2])) < 0:
                k_apex, l_apex = l_apex, k_apex
            hi.append(a)
            hj.append(b)
            hk.append(k_apex)
            hl.append(l_apex)
            sgn.append({"mountain": 1.0, "valley": -1.0, "facet": 0.0}[asg])
        self.hi, self.hj, self.hk, self.hl = (np.array(x) for x in (hi, hj, hk, hl))
        self.sgn = np.array(sgn)

        # --- length-projection constraints: every real (non-border) edge. -----
        real_edges = [e for e in pattern.edges if e.assignment != "border"]
        self.ea = np.array([e.v0 for e in real_edges])
        self.eb = np.array([e.v1 for e in real_edges])
        self.rest = np.linalg.norm(self.flat[self.eb] - self.flat[self.ea], axis=1)
        deg = np.zeros(V)
        np.add.at(deg, self.ea, 1.0)
        np.add.at(deg, self.eb, 1.0)
        self.inv_deg = 1.0 / np.maximum(deg, 1.0)

        hub_ids = {v for f in pattern.faces if f.ring_index == 0 for v in f.vertex_ids}
        self.pinned = np.array([i in hub_ids for i in range(V)])

    # --- FK predictor ---------------------------------------------------------

    def _face_poses(self, t: float) -> tuple[np.ndarray, np.ndarray]:
        n_faces = len(self.pattern.faces)
        R = np.zeros((n_faces, 3, 3))
        T = np.zeros((n_faces, 3))
        R[0] = np.eye(3)
        angle = MAX_BEND * t
        for face_id in self.bfs_order[1:]:
            parent_id, _ = self.parent[face_id]
            Rp, Tp = R[parent_id], T[parent_id]
            v0, v1 = self.hinge_v0[face_id], self.hinge_v1[face_id]
            pivot = Rp @ self.flat[v0] + Tp
            axis_dir = Rp @ (self.flat[v1] - self.flat[v0])
            axis_norm = np.linalg.norm(axis_dir)
            sign = self.hinge_sign[face_id]
            if axis_norm < 1e-12 or sign == 0.0:
                Rh = np.eye(3)
            else:
                Rh = _rotation_matrix(axis_dir / axis_norm, sign * angle)
            R[face_id] = Rh @ Rp
            T[face_id] = pivot - Rh @ pivot + Rh @ Tp
        return R, T

    def _predict(self, t: float) -> np.ndarray:
        R, T = self._face_poses(t)
        sums = np.zeros((self.n_out, 3))
        counts = np.zeros(self.n_out)
        for face, vids in zip(self.pattern.faces, self.face_vertex_ids):
            Rf, Tf = R[face.id], T[face.id]
            for vid in vids:
                sums[vid] += Rf @ self.flat[vid] + Tf
                counts[vid] += 1
        counts[counts == 0] = 1.0
        return sums / counts[:, None]

    # --- relaxation refinement -------------------------------------------------

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

    def _repel(self, X):
        pairs = cKDTree(X).query_pairs(MIN_SEPARATION, output_type="ndarray")
        if len(pairs) == 0:
            return
        i, j = pairs[:, 0], pairs[:, 1]
        flat_d = np.linalg.norm(self.flat[i, :2] - self.flat[j, :2], axis=1)
        far = flat_d > REPEL_FLAT_EXCLUDE
        i, j = i[far], j[far]
        if len(i) == 0:
            return
        d = X[j] - X[i]
        dist = np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-6)
        push = np.maximum(MIN_SEPARATION - dist[:, 0], 0.0)[:, None] * (d / dist) * REPEL_GAIN
        F = np.zeros_like(X)
        np.add.at(F, i, -push)
        np.add.at(F, j, push)
        F[self.pinned] = 0.0
        X += F

    def _refine(self, X: np.ndarray, t: float) -> np.ndarray:
        vel = np.zeros_like(X)
        target = self.sgn * MAX_BEND * t
        for _ in range(SUBSTEPS):
            F = np.zeros_like(X)
            th, g1, g2, g3, g4 = self._dihedral(X)
            c = (-BEND * (th - target))[:, None]
            np.add.at(F, self.hi, c * g1)
            np.add.at(F, self.hj, c * g2)
            np.add.at(F, self.hk, c * g3)
            np.add.at(F, self.hl, c * g4)
            F[self.pinned] = 0.0
            vel = (vel + DT * F) * DAMP
            X = X + DT * vel
            X[self.pinned, 2] = self.flat[self.pinned, 2]
            self._project_lengths(X)
            self._repel(X)
        return X

    def solve_sweep(self):
        samples = [s / STEPS for s in range(STEPS + 1)]
        frames = []
        for t in samples:
            X = self._predict(t)
            X = self._refine(X, t)
            frames.append(np.round(X, 4).reshape(-1).tolist())
        return samples, frames


def solve_sweep(pattern: CreasePattern, params: FlasherParams):
    return FlasherFoldSolver(pattern, params).solve_sweep()
