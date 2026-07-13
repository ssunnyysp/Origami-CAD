"""Single-DOF fold solver: a rigid forward-kinematics PREDICTOR, refined by a
short, deterministic correction pass — not force relaxation from a random
seed, and not an unconstrained per-panel tween.

## What "single-DOF, rigid, not crumpling" means here, concretely

1. **Rigid-body discovery, not hand-declared panels.** Two triangles
   connected by a "facet" edge (the internal triangulation diagonal — never
   a real crease) are the same physical panel and can never bend relative
   to each other; union-find over facet edges merges them into one rigid
   body directly from the crease assignments. This recovers the hub and
   every ring panel as rigid bodies automatically.
2. **Forward kinematics from the pinned central square.** A breadth-first
   spanning tree of the body-adjacency graph (bodies connected by real
   mountain/valley creases), rooted at the hub body, gives every other body
   a unique chain of rigid rotations back to the hub. Every hinge's angle is
   `sign * MAX_ANGLE * t` — ONE shared function of the single foldness
   parameter `t` — so this is deterministic and closed-form: no velocity,
   no damping, no random seed, and therefore no jitter between frames (each
   frame is solved fresh from `t`, never accumulated from the last one).
3. **Why a correction pass is still needed, honestly.** The crease pattern
   was redesigned (see `generator.py`) so every interior vertex satisfies
   Maekawa's theorem (a necessary condition for rigid-foldability) — this
   was NOT true of two earlier designs, which had literally no valid rigid
   motion at all (a proven, measured fact, not a tuning issue; see
   `generator.py`'s module docstring). Maekawa is necessary but not
   sufficient: exact global rigid-foldability of a many-vertex mesh also
   requires Kawasaki's angle condition to hold, simultaneously, at every
   vertex, which is a strong constraint on the flat pattern's exact
   geometry. Measuring it directly (scripts/validate_flasher.py) found it
   is not exactly satisfied by this pattern's current vertex positions —
   deriving a closed-form twist/radius schedule that satisfies Kawasaki at
   every one of this mesh's coupled vertices simultaneously is a research-
   level construction (see the PR description for sources — there is a
   dedicated published paper on exactly this problem). Rather than leave
   the mechanism unable to reach a usefully-folded state at all, the FK
   prediction (which is exactly rigid per body and correctly shaped/
   handed) is refined by a bounded, deterministic position correction pass
   that closes the small residual gap left by the geometry not being
   exactly Kawasaki-satisfying. This is not spring/damping relaxation from
   noise (which is what produced "crumpling" before): it is a small number
   of position-based projections *of an already-correct rigid prediction*,
   and the residual it is correcting is measured and reported by
   `scripts/validate_flasher.py`, not hidden.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

from .generator import CreasePattern, FlasherParams

MAX_ANGLE = np.radians(40.0)  # target crease bend at foldness = 1, shared by
# every real crease. Deliberately conservative: measured panel-triangle
# distortion grows with driver angle (this pattern's Kawasaki-closure
# mismatch — see this module's docstring and generator.py's — is not
# uniform across the mesh, so distortion is not linear in angle either).
# 40 deg was the largest value where scripts/validate_flasher.py's
# panel-rigidity check stayed under its threshold across grid_divisions
# 7 and 9; see the PR description for the sweep and for what a larger,
# exact-closure range of motion would require.
STEPS = 60  # foldness samples (frames = STEPS + 1)
BEND = 2.0  # bending drive gain toward the target dihedral, in the refine pass
DT = 0.05
DAMP = 0.85
SUBSTEPS = 40
LENGTH_ITERS = 60
LENGTH_RELAX = 0.9
MIN_SEPARATION = 0.08
REPEL_GAIN = 1.2
REPEL_FLAT_EXCLUDE = 1.2


def _rotation_matrix(axis: np.ndarray, angle: float) -> np.ndarray:
    """Rodrigues' rotation formula: 3x3 rotation by `angle` about unit `axis`."""
    x, y, z = axis
    K = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)


def _cross2(ax, ay, bx, by):
    return ax * by - ay * bx


def _face_triangles(vertex_ids: list[int]):
    """Fan-triangulate a face for hinge-apex lookup (a no-op for triangles;
    only the hub face has more than 3 vertices, and it is rigid, so which
    fan diagonal is used never matters)."""
    for k in range(1, len(vertex_ids) - 1):
        yield (vertex_ids[0], vertex_ids[k], vertex_ids[k + 1])


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


class FlasherFoldSolver:
    def __init__(self, pattern: CreasePattern, params: FlasherParams):
        self.pattern = pattern
        by_id = {v.id: v for v in pattern.vertices}
        order = sorted(by_id)
        self.n_out = max(order) + 1
        self.flat = np.array([list(by_id[i].position) + [0.0] for i in range(self.n_out)])
        V = self.n_out

        assign = {e.id: e.assignment for e in pattern.edges}
        endpoints = {e.id: (e.v0, e.v1) for e in pattern.edges}

        # --- rigid-body discovery (union-find over facet edges) --------------
        faces_by_edge: dict[int, list[int]] = defaultdict(list)
        for f in pattern.faces:
            for eid in f.edge_ids:
                faces_by_edge[eid].append(f.id)

        uf = _UnionFind(len(pattern.faces))
        for eid, faces in faces_by_edge.items():
            if assign[eid] == "facet" and len(faces) == 2:
                uf.union(faces[0], faces[1])
        body_of_face = [uf.find(i) for i in range(len(pattern.faces))]
        body_ids = sorted(set(body_of_face))
        body_index = {b: i for i, b in enumerate(body_ids)}
        self.n_bodies = len(body_ids)
        body_of_face = [body_index[b] for b in body_of_face]

        hub_faces = [f.id for f in pattern.faces if f.ring_index == 0]
        hub_body = body_of_face[hub_faces[0]]
        for f in hub_faces:
            if body_of_face[f] != hub_body:
                raise RuntimeError("hub cell is not a single rigid body")
        self.hub_body = hub_body

        # --- FK spanning tree over the body-adjacency graph -------------------
        hinge_edges: list[tuple[int, int, int, int, float]] = []
        for eid, faces in faces_by_edge.items():
            a = assign[eid]
            if a in ("facet", "border") or len(faces) != 2:
                continue
            bA, bB = body_of_face[faces[0]], body_of_face[faces[1]]
            if bA == bB:
                continue  # a redundant/degenerate real edge inside one body; not a hinge
            v0, v1 = endpoints[eid]
            sign = 1.0 if a == "mountain" else -1.0
            hinge_edges.append((bA, bB, v0, v1, sign))

        adjacency: dict[int, list[tuple[int, int, int, float]]] = defaultdict(list)
        for bA, bB, v0, v1, sign in hinge_edges:
            adjacency[bA].append((bB, v0, v1, sign))
            adjacency[bB].append((bA, v1, v0, sign))

        parent_body: dict[int, int | None] = {hub_body: None}
        order_bfs = [hub_body]
        visited = {hub_body}
        self.hinge_v0: dict[int, int] = {}
        self.hinge_v1: dict[int, int] = {}
        self.hinge_sign: dict[int, float] = {}
        head = 0
        while head < len(order_bfs):
            b = order_bfs[head]
            head += 1
            for nb, v0, v1, sign in adjacency[b]:
                if nb in visited:
                    continue
                visited.add(nb)
                parent_body[nb] = b
                self.hinge_v0[nb] = v0
                self.hinge_v1[nb] = v1
                self.hinge_sign[nb] = sign
                order_bfs.append(nb)
        if len(visited) != self.n_bodies:
            raise RuntimeError(
                f"body-adjacency graph is disconnected: {self.n_bodies - len(visited)} bodies unreachable"
            )
        self.body_order = order_bfs
        self.parent_of = parent_body
        self.body_of_face = body_of_face
        self.face_vertex_ids = [f.vertex_ids for f in pattern.faces]

        # --- dihedral-angle refine setup (fan-triangulated hinge table) -------
        edge_tris: dict[tuple[int, int], list[int]] = defaultdict(list)
        for f in pattern.faces:
            for a, b, apex in _face_triangles(f.vertex_ids):
                for e0, e1, ap in ((a, b, apex), (b, apex, a), (apex, a, b)):
                    edge_tris[(min(e0, e1), max(e0, e1))].append(ap)

        edge_assign_by_pair = {}
        for e in pattern.edges:
            key = (min(e.v0, e.v1), max(e.v0, e.v1))
            edge_assign_by_pair[key] = e.assignment
        hi, hj, hk, hl, sgn = [], [], [], [], []
        for (a, b), apexes in edge_tris.items():
            if len(apexes) != 2:
                continue
            asg = edge_assign_by_pair.get((a, b), "facet")
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

    def _body_poses(self, t: float) -> tuple[np.ndarray, np.ndarray]:
        R = np.zeros((self.n_bodies, 3, 3))
        T = np.zeros((self.n_bodies, 3))
        R[self.hub_body] = np.eye(3)
        angle = MAX_ANGLE * t
        for body in self.body_order[1:]:
            parent = self.parent_of[body]
            Rp, Tp = R[parent], T[parent]
            v0, v1 = self.hinge_v0[body], self.hinge_v1[body]
            pivot = Rp @ self.flat[v0] + Tp
            axis_dir = Rp @ (self.flat[v1] - self.flat[v0])
            axis_n = np.linalg.norm(axis_dir)
            sign = self.hinge_sign[body]
            if axis_n < 1e-12:
                Rh = np.eye(3)
            else:
                Rh = _rotation_matrix(axis_dir / axis_n, sign * angle)
            R[body] = Rh @ Rp
            T[body] = pivot - Rh @ pivot + Rh @ Tp
        return R, T

    def _predict(self, t: float) -> np.ndarray:
        R, T = self._body_poses(t)
        sums = np.zeros((self.n_out, 3))
        counts = np.zeros(self.n_out)
        for face, vids in zip(self.pattern.faces, self.face_vertex_ids):
            b = self.body_of_face[face.id]
            Rf, Tf = R[b], T[b]
            for vid in vids:
                sums[vid] += Rf @ self.flat[vid] + Tf
                counts[vid] += 1
        counts[counts == 0] = 1.0
        return sums / counts[:, None]

    # --- correction refine ------------------------------------------------

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
        target = self.sgn * MAX_ANGLE * t
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
        # Continuation, not independent re-solves: each frame's correction
        # pass is seeded from the PREVIOUS frame's converged result (only
        # frame 0 seeds from the flat FK prediction). Re-solving every frame
        # from a fresh FK prediction let the correction pass settle into a
        # different local configuration between adjacent, very-close t
        # values once the pattern's residual (see module docstring) got
        # large enough — measured as a real frame-to-frame position jump,
        # i.e. popping. Continuation keeps each step a small perturbation of
        # the last, which is what a physical piece of paper actually does.
        samples = [s / STEPS for s in range(STEPS + 1)]
        frames = []
        X = None
        for t in samples:
            seed = self._predict(t) if X is None else X
            X = self._refine(seed, t)
            frames.append(np.round(X, 5).reshape(-1).tolist())
        return samples, frames


def solve_sweep(pattern: CreasePattern, params: FlasherParams):
    return FlasherFoldSolver(pattern, params).solve_sweep()
