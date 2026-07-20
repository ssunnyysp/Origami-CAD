"""Rigid-motion-interpolation fold solver.

The crease pattern is EXACT: folding every crease to its target dihedral
angle (180° for pleats, 90° for the wrap's vertical corner bends, signed by
mountain/valley) closes the sheet into a 1×1×1 box at machine precision —
checked by a loop-closure oracle (fold every face along a spanning tree
rooted at the hub; a correct pattern makes every vertex's position agree
across all its faces, for every odd n).

That exactness is the whole foundation of this solver, and it rules out two
approaches that were tried and failed here first:

1. TREE-FOLD RECONSTRUCTION PER FRAME (composing hinge rotations along the
   spanning tree at each frame's PARTIAL fold angle, then averaging
   disagreeing face copies of each vertex) looks reasonable at a glance —
   it's exact at t=0 and t=1 — but in between, a flasher sheet is not a
   rigid mechanism (Lang, J. Mechanisms & Robotics 2016), so different
   faces reached via different loop paths disagree about a shared vertex's
   position. Measured directly: at t≈0.3 the disagreement is on the order
   of 50-75% of the sheet's own size — not a small residual to smooth over,
   but the dominant signal. Averaging that produces exactly the spiky,
   self-intersecting crumple this project's users reported ("phasing
   through", "crunching"); no amount of post-hoc smoothing fixes a target
   that is itself mostly noise.
2. PURE DIHEDRAL-ANGLE DYNAMICS FROM THE FLAT SHEET (a force per crease
   pulling its dihedral angle toward a scheduled target, integrated with
   damping from t=0) is the right *kind* of model — verified correct on an
   isolated single hinge — but on the full ~300-hinge network starting from
   flat, it stalls: mean angle error plateaus around 40° regardless of how
   much gain, damping, or substep budget is thrown at it. The coupled
   system can't discover the large coordinated rotate-and-compact motion
   from purely local torques and a flat start; it needs to already be
   pointed roughly the right way.

The fix used here combines them so each covers the other's failure mode:
for each frame, take every face's FULL rigid transform at the exact t=1
closure (well-defined and mutually consistent, since t=1 provably closes),
and SLERP each face's rotation from identity toward that fixed target by
the frame's own schedule fraction (translation is lerped the same way).
This is closed-form and stable — never touches the noisy partially-tree-
folded intermediate states above — and it already captures the correct
large-scale rotate-and-compact motion because it's interpolating toward a
verified-correct answer. Independently interpolating each face does open
small seams between adjacent faces (their SLERP curves only agree at the
endpoints), so a short relaxation pass — the same dihedral-angle force as
approach (2), now just reconciling a nearly-right guess instead of
discovering the whole motion — plus edge-length projection and self-
collision repulsion, cleans that up into a smooth, valid, inextensible
shape every frame. A displacement rate limit (`MAX_STEP_PER_FRAME`) and
heavy previous-frame blending keep frame-to-frame motion continuous even
though each frame's SLERP target is computed independently.

Relaxation iteration budget (`relax_substeps`, `length_iters`) scales with
ring count, since more rings means longer hinge chains and more seam
residual to reconcile each frame — but it's capped (`MAX_RELAX_SUBSTEPS`,
`MAX_LENGTH_ITERS`): growing it unboundedly made the largest preset (31x31,
15 rings) take minutes for diminishing convergence return. Measured on
this project's four presets, relaxed enough to keep the largest solving in
well under a minute: the default 7x7 preset converges close to the exact
1x1x1 stow (final strain ~4%); the 31x31 "Big Bang" preset is smooth and
self-intersection-free but converges less fully in the time budget (looser,
not as tightly compacted). `_project_lengths`'s scatter-add uses a
precomputed sparse incidence matrix rather than `np.add.at`, which
profiling found to be the dominant per-substep cost (~85% of it) on the
largest preset — the sparse matvec is the same accumulation, just much
faster since the mesh topology never changes across iterations.

WHY THE FOLD DOESN'T LOOK LIKE IT'S ROTATING, AND THE FIX: pinning the hub
(holding it at identity rotation for all t, as this solver's internal
dynamics does) is a GAUGE CHOICE — the crease constraints only pin down
each panel's motion *relative to its neighbors*, so which single panel gets
held fixed while everything else is expressed relative to it is free to
choose, and rotating that choice can't change any edge length or dihedral
angle (a global rigid motion is an isometry). Pinning the hub happens to be
a bad choice for visual clarity here: the exact closure (verified by the
oracle) shows each ring's rotation *relative to the ring inside it*
alternates sign — ring 2 sits at -90° relative to ring 1, but ring 3 sits
at +90° relative to ring 2, landing back near ring 1's own angle. That
alternation is a real, unavoidable consequence of the accordion pleat
(adjacent rings must lean opposite ways to stack compactly, the same
reason bellows pleats alternate) — not a bug, and not fixable by choosing
different creases. But it means that in the hub-pinned frame, the
outermost material's NET rotation partially cancels and reads as barely
rotating at all, even though every individual ring is turning throughout.
The fix is to stop pinning the hub for *display* purposes: `GLOBAL_SPIN`
below applies one additional rigid rotation to the entire frame (hub
included) as a pure post-processing step, monotonically increasing with
foldness. It never touches the internal solve (seed, relaxation, rate
limiting all still run in the hub-pinned frame exactly as validated), so it
can't affect strain, self-intersection, or closure — it only changes which
gauge the *output* is expressed in, the same free choice a real flasher's
"twist fold" actuation makes when someone turns the whole assembly by hand.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque

import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from .generator import HUB_HALF, CreasePattern, FlasherParams

STEPS = 60  # foldness samples (frames = STEPS + 1)
CAP = 170.0 / 180.0  # fraction of the exact stow angles driven at t=1, so
# stowed layers stay visually separated instead of pressing exactly flat
BEND_GAIN = 2.0  # dihedral-angle reconciliation force gain
DT = 0.015
DAMP = 0.8
RELAX_SUBSTEPS_PER_RING = 100 / 3  # relaxation substeps per frame, scaled by
# ring count: more rings means longer hinge chains and more seam residual
# to reconcile each frame, found by direct measurement across grid sizes.
# Capped below — growing this unboundedly with ring count makes the
# largest preset (31x31, 15 rings) take minutes instead of seconds for
# diminishing convergence return; the cap trades some residual strain on
# the biggest presets for a solve that finishes in a reasonable time.
LENGTH_ITERS_PER_RING = 25 / 3
MAX_RELAX_SUBSTEPS = 90
MAX_LENGTH_ITERS = 16
LENGTH_RELAX = 0.9
PREV_BLEND = 0.5  # weight of the previous frame when seeding relaxation
MAX_STEP_PER_FRAME = 0.35  # per-vertex displacement cap between frames —
# makes a discontinuous jump ("pulse") impossible regardless of how far the
# raw SLERP target moves in a single foldness step
MIN_SEPARATION = 0.08  # closest two flat-far vertices are allowed to get
REPEL_GAIN = 1.0
REPEL_FLAT_EXCLUDE = 1.6  # skip pairs this close in the FLAT pattern — two
# sides of the same pleat are meant to swing close together; only pairs far
# apart in the flat sheet but close in 3-D are genuine self-intersection

GLOBAL_SPIN_DEGREES_PER_RING = 60.0  # display-only rigid spin (see module
# docstring "WHY THE FOLD DOESN'T LOOK LIKE IT'S ROTATING"): applied to the
# whole frame, monotonically with foldness, independent of the hub-pinned
# internal solve. Scales with ring count so more complex folds visibly turn
# proportionally more, capped so the largest preset doesn't spin too fast
# to read as a clean rotation.
MAX_GLOBAL_SPIN_DEGREES = 720.0


def _cross2(ax, ay, bx, by):
    return ax * by - ay * bx


class FlasherFoldSolver:
    def __init__(self, pattern: CreasePattern, params: FlasherParams):
        self.params = params
        by_id = {v.id: v for v in pattern.vertices}
        self.n_out = max(by_id) + 1
        self.flat = np.array([list(by_id[i].position) + [0.0] for i in range(self.n_out)])
        V = self.n_out
        rings = max(pattern.ring_count, 1)
        self.relax_substeps = min(MAX_RELAX_SUBSTEPS, max(20, round(RELAX_SUBSTEPS_PER_RING * rings)))
        self.length_iters = min(MAX_LENGTH_ITERS, max(10, round(LENGTH_ITERS_PER_RING * rings)))
        self.global_spin_radians = math.radians(
            min(MAX_GLOBAL_SPIN_DEGREES, GLOBAL_SPIN_DEGREES_PER_RING * rings)
        )

        assign = {
            (min(e.v0, e.v1), max(e.v0, e.v1)): (e.assignment, e.fold_factor)
            for e in pattern.edges
        }
        edge_tris: dict[tuple[int, int], list[int]] = defaultdict(list)
        for f in pattern.faces:
            t = f.vertex_ids
            for a, b, apex in ((t[0], t[1], t[2]), (t[1], t[2], t[0]), (t[2], t[0], t[1])):
                edge_tris[(min(a, b), max(a, b))].append(apex)

        hi, hj, hk, hl, sign, mag = [], [], [], [], [], []
        for (a, b), apexes in edge_tris.items():
            if len(apexes) != 2:
                continue
            asg, factor = assign.get((a, b), ("facet", 1.0))
            if asg == "border":
                continue
            d = self.flat[b, :2] - self.flat[a, :2]
            k, l = apexes
            if _cross2(d[0], d[1], *(self.flat[k, :2] - self.flat[a, :2])) < 0:
                k, l = l, k
            hi.append(a); hj.append(b); hk.append(k); hl.append(l)
            sign.append({"mountain": 1.0, "valley": -1.0, "facet": 0.0}[asg])
            mag.append(np.pi * factor)
        self.hi, self.hj, self.hk, self.hl = map(np.array, (hi, hj, hk, hl))
        self.sign, self.mag = np.array(sign), np.array(mag)

        self.ea = np.array([a for a, _ in edge_tris])
        self.eb = np.array([b for _, b in edge_tris])
        self.rest = np.linalg.norm(self.flat[self.eb] - self.flat[self.ea], axis=1)
        deg = np.zeros(V)
        np.add.at(deg, self.ea, 1.0)
        np.add.at(deg, self.eb, 1.0)
        self.inv_deg = 1.0 / np.maximum(deg, 1.0)
        # Sparse vertex<-edge incidence matrix: scatter-adding `corr` into
        # `dX` every length-projection iteration via np.add.at is, for a
        # mesh this size, the dominant cost of the whole solve (measured:
        # ~85% of per-substep time on the 31x31 preset) — np.add.at doesn't
        # vectorize scatter-with-duplicate-indices well. A sparse matvec
        # against a fixed incidence matrix does the same accumulation an
        # order of magnitude faster since the topology never changes.
        n_edges = len(self.ea)
        self._incidence = sparse.csr_matrix(
            (
                np.concatenate([np.ones(n_edges), -np.ones(n_edges)]),
                (
                    np.concatenate([self.ea, self.eb]),
                    np.concatenate([np.arange(n_edges), np.arange(n_edges)]),
                ),
            ),
            shape=(V, n_edges),
        )

        # Pin the hub square flat — the central square all the rest folds around.
        rho = np.maximum(np.abs(self.flat[:, 0]), np.abs(self.flat[:, 1]))
        self.pinned = rho <= HUB_HALF + 1e-9

        edges = {e.id: e for e in pattern.edges}
        faces = {f.id: f for f in pattern.faces}
        adj = {a["faceId"]: a["neighbors"] for a in pattern.adjacency}
        hub = next(f.id for f in pattern.faces if f.ring_index == 0)
        self.hub = hub
        self.n_faces = len(pattern.faces)
        self.face_vids = np.array([faces[i].vertex_ids for i in range(self.n_faces)])

        # Compose each face's full rigid transform at the exact t=1 (CAP-scaled)
        # closure, once, via a BFS spanning tree from the hub.
        seen = {hub}
        R: list = [None] * self.n_faces
        Tt: list = [None] * self.n_faces
        R[hub] = np.eye(3)
        Tt[hub] = np.zeros(3)
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
                if e.assignment in ("facet", "border"):
                    Rl, tl = np.eye(3), np.zeros(3)
                else:
                    s = {"mountain": 1.0, "valley": -1.0}[e.assignment]
                    phi = s * np.pi * e.fold_factor * CAP
                    a_ = -side * phi
                    dn = d / np.linalg.norm(d)
                    c, sn = np.cos(a_), np.sin(a_)
                    K = np.array([[0, -dn[2], dn[1]], [dn[2], 0, -dn[0]], [-dn[1], dn[0], 0]])
                    Rl = np.eye(3) + sn * K + (1 - c) * (K @ K)
                    tl = p0 - Rl @ p0
                R[g] = R[f] @ Rl
                Tt[g] = R[f] @ tl + Tt[f]
                queue.append(g)
        self.t_final = np.array(Tt)
        self._rot_final = Rotation.from_matrix(np.array(R))

    def _face_pose(self, s: float):
        """Every face's rotation SLERPed from identity toward its final
        rotation by fraction s in [0,1]; translation lerped the same way."""
        if s <= 0.0:
            R = np.tile(np.eye(3), (self.n_faces, 1, 1))
            t = np.zeros((self.n_faces, 3))
            return R, t
        R = Rotation.from_rotvec(self._rot_final.as_rotvec() * s).as_matrix()
        return R, self.t_final * s

    def _seed(self, s: float) -> np.ndarray:
        R, t = self._face_pose(s)
        pts = np.einsum("fij,fvj->fvi", R, self.flat[self.face_vids]) + t[:, None, :]
        ids = self.face_vids.reshape(-1)
        acc = np.zeros((self.n_out, 3))
        cnt = np.zeros(self.n_out)
        np.add.at(acc, ids, pts.reshape(-1, 3))
        np.add.at(cnt, ids, 1.0)
        return acc / np.maximum(cnt, 1.0)[:, None]

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

    def _project_lengths(self, X: np.ndarray) -> None:
        for _ in range(self.length_iters):
            d = X[self.eb] - X[self.ea]
            L = np.linalg.norm(d, axis=1, keepdims=True)
            corr = (L - self.rest[:, None]) * (d / np.maximum(L, 1e-9)) * LENGTH_RELAX
            dX = self._incidence @ corr  # sparse matvec: same scatter-add as
            # np.add.at(dX, ea, corr); np.add.at(dX, eb, -corr), an order of
            # magnitude faster since the incidence matrix is precomputed once
            dX *= self.inv_deg[:, None]
            dX[self.pinned] = 0.0
            X += dX

    def _repel(self, X: np.ndarray) -> None:
        """Push apart vertex pairs close in 3-D but far apart in the flat
        sheet — genuine self-intersection, not two sides of a pleat meeting
        as intended."""
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

    @staticmethod
    def _smoothstep(u: float) -> float:
        u = min(max(u, 0.0), 1.0)
        return u * u * (3.0 - 2.0 * u)

    def _spun_for_display(self, X: np.ndarray, s: float) -> np.ndarray:
        """Rigid Z-rotation of the whole frame by the display-only global
        spin (see module docstring) — an isometry, so it cannot change any
        edge length or dihedral angle. Purely a choice of which panel's
        orientation the *output* is expressed relative to; the internal
        hub-pinned solve above is completely unaffected."""
        angle = self.global_spin_radians * s
        c, sn = math.cos(angle), math.sin(angle)
        Xs = X.copy()
        Xs[:, 0] = c * X[:, 0] - sn * X[:, 1]
        Xs[:, 1] = sn * X[:, 0] + c * X[:, 1]
        return Xs

    def solve_sweep(self):
        frames = [np.round(self.flat, 4).reshape(-1).tolist()]
        samples = [0.0]
        X_prev: np.ndarray | None = None
        for step in range(1, STEPS + 1):
            t = step / STEPS
            s = self._smoothstep(t)
            target = self.sign * self.mag * CAP * s

            X = self._seed(s)
            if X_prev is not None:
                X = (1 - PREV_BLEND) * X + PREV_BLEND * X_prev
                d = X - X_prev
                dist = np.linalg.norm(d, axis=1, keepdims=True)
                scale = np.minimum(1.0, MAX_STEP_PER_FRAME / np.maximum(dist, 1e-9))
                X = X_prev + d * scale

            vel = np.zeros_like(X)
            for _ in range(self.relax_substeps):
                F = np.zeros_like(X)
                th, g1, g2, g3, g4 = self._dihedral(X)
                err = th - target
                err = np.mod(err + np.pi, 2 * np.pi) - np.pi
                c = (-BEND_GAIN * err)[:, None]
                np.add.at(F, self.hi, c * g1)
                np.add.at(F, self.hj, c * g2)
                np.add.at(F, self.hk, c * g3)
                np.add.at(F, self.hl, c * g4)
                F[self.pinned] = 0.0
                vel = (vel + DT * F) * DAMP
                X = X + DT * vel
                X[self.pinned, 2] = 0.0
                self._project_lengths(X)
                self._repel(X)
            X_prev = X  # unrotated — the rate limiter and next seed blend
            # always operate in the stable hub-pinned frame that was tuned
            # and validated for strain/self-intersection/closure
            frames.append(np.round(self._spun_for_display(X, s), 4).reshape(-1).tolist())
            samples.append(t)
        return samples, frames


def solve_sweep(pattern: CreasePattern, params: FlasherParams):
    return FlasherFoldSolver(pattern, params).solve_sweep()
