"""Flasher fold solver — forward simulation with the ACCORDION PLEATS leading.

The wrap-pinwheel crease pattern folds by the accordion PLEATS in each region
forming a WAVE — alternating mountain ridges (up) and valley troughs (down) —
and that wave compressing to wrap the sheet around the central hub. Two rules,
learned from how the pattern actually folds, make this come out right and are
the whole reason earlier solvers crumpled instead:

  1. THE PLEATS LEAD, THE DIAGONAL ONLY AIDS. Each region's 45° diagonal is
     NOT a guiding fold and must not take precedence over the pleats. If the
     diagonal is driven as hard as the pleats it fights them and the region
     crumples instead of forming its clean up/down wave. So the diagonal
     creases are given a small weight (`DIAGONAL_WEIGHT`): they fold only
     passively, as much as the surrounding pleats leave room for — exactly
     the "aids the flasher to fold nicely" role. The pleats and the hub-wall
     bends are driven at full weight and reach their declared angles, so the
     mountain/valley wave forms crisply (measured: ~100% of pleats fold in
     their declared direction).

  2. FACETS STAY (NEARLY) RIGID so the bending happens ON the crease lines.
     The X-triangulation diagonals inside every cell are held toward flat
     (`FACET_WEIGHT`), so each cell stays a flat panel and the fold is sharp
     at the pleats rather than smeared across a wavy surface. A little flex is
     allowed (the pattern is not perfectly rigidly foldable — Lang, J.
     Mechanisms Robotics 2016), but only single digits of degrees.

Method: position-based dynamics, simulated FORWARD from the flat sheet (the
Origami-Simulator approach). Each frame ramps the crease targets a little
further, then per substep projects: edge lengths (inextensible), self-
collision (folded layers stack, don't pass through each other), and finally
the dihedral targets (creases + facets, weighted as above) LAST so the crease
pattern dominates. Positions carry forward frame to frame. The hub cell is
pinned flat as the fixed centre everything wraps around.

How FAR it folds at foldness=1: every crease is driven to the FULL angle the
crease pattern declares (`CAP` = 1.0) on every preset. What varies per preset
is `SUBSTEPS`, the amount of settling — the fold has to propagate outward from
the pinned hub one ring at a time, so sheets with more rings need more passes
to converge, and starved of them they stow loose. Scaling settling with ring
count (plus a constant `COLLISION_SEP`, see below) is what makes the large
grids wrap as tightly as the small ones instead of looser.

Output frames are vertex positions indexed by the generator's original vertex
ids (the mesh is used welded, as generated — no vertex splitting), which is
the contract main.py and the frontend consume.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

from .generator import HUB_HALF, CreasePattern, FlasherParams

STEPS = 60  # foldness samples returned (frames = STEPS + 1)

# CAP — the fraction of each crease's full declared angle driven at
# foldness=1. 1.0 means every crease is driven to the FULL angle the crease
# pattern declares, which is what "100% folded" ought to mean; it is also a
# hard ceiling, since a target past 180° wraps around in the angle convention
# used by _project_dihedrals and would flip the fold direction.
#
# CAP used to be scaled down per preset because the large grids self-
# intersected before reaching their declared angles. That turned out to be a
# symptom of COLLISION_SEP being too small on those presets, not of the fold
# depth itself (see COLLISION_SEP below). With the separation fixed, all four
# presets reach 1.00 with ZERO true triangle-triangle intersections, 100%
# mountain/valley sign fidelity, and <=9.6% mean strain, so the per-preset
# scaling is gone.
CAP = 1.0

# SUBSTEPS — PBD settle passes per frame, and THE fold-depth dial now that CAP
# is pinned at 1.0. The fold has to propagate from the pinned hub outward one
# ring at a time, so a sheet with more rings needs proportionally more settling
# before it is converged; starved of passes it stops early and stows loose.
# Scaling with ring count is what fixed the "big grids wrap LOOSER than small
# ones" inversion. Measured at CAP=1.0 (wrap radius, lower = tighter):
#   7x7    substeps 16 -> 0.437, 32 -> 0.425, 64 -> 0.411, 128 -> 0.408
#   15x15  substeps 24 -> 0.416, 48 -> 0.379, 96 -> 0.377
#   23x23  substeps 32 -> 0.484, 64 -> 0.432, 128 -> 0.376
#   31x31  substeps 40 -> 0.516, 80 -> 0.479, 128 -> 0.447, 160 -> 0.427
# The small grids flatten out by ~64-96; the large ones are still improving at
# the cap. SUBSTEPS_MAX is set by SOLVE TIME, not by the curve: 31x31 at 160
# takes ~98 s (~77 s at 128, ~47 s at 80). Paid once per parameter set via the
# lru_cache in main.py, never per frame, and the UI shows a solving state
# meanwhile — but if that wait is too long, LOWER SUBSTEPS_MAX; it is the one
# knob trading fold depth against first-load time.
#
# Spend extra effort HERE rather than on DIHEDRAL_ITERS: more dihedral
# iterations per substep reach a similar depth but with far worse strain
# (31x31 at substeps 16/iters 18 gave 15.2% mean strain vs 9.3% at substeps
# 32/iters 6, and took longer).
#
# NOTE: driving this deep REQUIRES the matching COLLISION_SEP below. At the
# old flat 0.60 the large grids start genuinely self-intersecting once they
# fold this far (23x23 at 128 substeps: 13 intersections; 31x31 at 80: 8).
SUBSTEPS_BASE = 40
SUBSTEPS_PER_RING = 8
SUBSTEPS_MIN = 64
SUBSTEPS_MAX = 160

# Settling is ramped over the sweep rather than spent uniformly: a frame at
# foldness 0.1 is nowhere near the pattern's over-constrained regime and
# converges almost immediately, while the last few frames are doing all the
# hard work. A frame gets `substeps * (FLOOR + (1-FLOOR)*frac)` passes, so the
# deep end runs at the full count and the shallow end at FLOOR of it. This
# costs a bit over half of a flat schedule for the same final depth, which is
# what makes the higher SUBSTEPS_MAX above affordable.
SUBSTEPS_RAMP_FLOOR = 0.25
SUBSTEPS_RAMP_MIN = 6  # never settle a frame with fewer passes than this

DIHEDRAL_ITERS = 6  # dihedral projection iterations per substep (run last so
# the crease pattern dominates the settled shape)
LENGTH_ITERS = 4
LENGTH_RELAX = 0.8  # near-inextensible, soft enough not to oscillate

# Per-hinge dihedral weights (relative pull toward the hinge's target angle):
PLEAT_WEIGHT = 1.0  # accordion pleats — lead the fold, form the wave
WALL_WEIGHT = 1.0  # the four hub-cell wall bends (90°) — lead too
DIAGONAL_WEIGHT = 0.1  # the region diagonals — PASSIVE aid only, must not
# take precedence over the pleats (see rule 1 above)
FACET_WEIGHT = 1.0  # X-triangulation diagonals — held toward flat so cells
# stay rigid panels and creases fold sharply (see rule 2 above). Full rigidity
# is viable here ONLY because the diagonal is passive (rule 1): with a leading
# diagonal, rigid facets used to force self-intersection; with the diagonal
# yielding, the pleats form the wave and the cells can stay flat. Measured:
# facet flex drops to 2-7° mean (sharp creases) with the pleats still folding
# 98-100% in their declared direction and zero self-intersection.

COLLISION_ITERS = 3
COLLISION_FLAT_EXCLUDE = 1.6  # only push apart pairs at least this far apart
# in the FLAT sheet (adjacent pleat walls are meant to come together)

# COLLISION_SEP — effective layer separation ("paper thickness") in grid units.
# Scales UP with ring count. Note this is the OPPOSITE of what this file used
# to do: it originally thinned with ring count (0.26 at 31x31) on the theory
# that a fine preset stows into many thin layers needing a smaller gap. That
# was measured to be exactly backwards and was the single thing capping the
# large grids — at 0.26 the 31x31 phased through itself badly at full fold
# (388 true intersections), which forced CAP down and left the big presets
# stowing LOOSER than the small ones.
#
# The rule that actually holds: clearance has to match how tightly the sheet
# wraps. The tighter the wrap, the more layers stack in the same space and the
# more margin the (proximity-based, vertex-pair) repulsion needs to keep them
# apart. Since fold depth now scales with ring count via SUBSTEPS above, so
# must this. Measured at the shipped substeps, holding everything else fixed:
#   7x7   sep 0.60 -> 0 intersections (0.70 would cost depth: wrap .411->.448)
#   15x15 sep 0.62 -> 0                        (0.70 -> wrap .389 -> .426)
#   23x23 sep 0.66 -> 0                        (0.60 -> 13 intersections)
#   31x31 sep 0.70 -> 0                        (0.60 ->  8 intersections)
# So it is bounded BELOW by phasing and ABOVE by wasted depth; the line below
# threads that. It is not itself a depth lever - within the safe band, varying
# it moves wrap by <0.01 - but setting it too low forces depth down elsewhere.
COLLISION_SEP_BASE = 0.55
COLLISION_SEP_PER_RING = 0.01
COLLISION_SEP_MIN = 0.60
COLLISION_SEP_MAX = 0.70

SEED_KICK = 0.01  # tiny random z offset on the flat seed so the first fold
# step has a direction to break out of the perfectly-flat plane


class FlasherFoldSolver:
    def __init__(self, pattern: CreasePattern, params: FlasherParams):
        self.params = params
        by_id = {v.id: v.position for v in pattern.vertices}
        self.V = max(by_id) + 1
        self.flat = np.array([list(by_id[i]) + [0.0] for i in range(self.V)])
        self.face_vids = np.array([f.vertex_ids for f in pattern.faces])

        def is_cell_center(vid: int) -> bool:
            # cell centers sit at integer flat coords; grid corners at ±0.5
            x, y = by_id[vid]
            return abs(x - round(x)) < 0.1 and abs(y - round(y)) < 0.1

        # Hinges: every interior edge shared by exactly two triangles, each
        # classified so its fold can be weighted (pleats/walls lead, diagonal
        # aids, facets stay flat).
        assign = {
            (min(e.v0, e.v1), max(e.v0, e.v1)): (e.assignment, e.fold_factor)
            for e in pattern.edges
        }
        edge_tris: dict[tuple[int, int], list[int]] = defaultdict(list)
        for t in self.face_vids:
            for a, b, apex in ((t[0], t[1], t[2]), (t[1], t[2], t[0]), (t[2], t[0], t[1])):
                edge_tris[(min(int(a), int(b)), max(int(a), int(b)))].append(int(apex))

        hi, hj, hk, hl, sign, mag, weight = [], [], [], [], [], [], []
        for (a, b), apexes in edge_tris.items():
            if len(apexes) != 2:
                continue
            asg, factor = assign.get((a, b), ("facet", 1.0))
            if asg == "border":
                continue
            d = self.flat[b, :2] - self.flat[a, :2]
            k, l = apexes
            if d[0] * (self.flat[k, 1] - self.flat[a, 1]) - d[1] * (self.flat[k, 0] - self.flat[a, 0]) < 0:
                k, l = l, k
            hi.append(a); hj.append(b); hk.append(k); hl.append(l)
            sign.append({"mountain": 1.0, "valley": -1.0, "facet": 0.0}[asg])
            mag.append(math.pi * factor)
            if asg == "facet":
                weight.append(FACET_WEIGHT)
            elif is_cell_center(a) or is_cell_center(b):
                weight.append(DIAGONAL_WEIGHT)  # region diagonal — passive aid
            elif factor == 0.5:
                weight.append(WALL_WEIGHT)  # hub-cell wall bend
            else:
                weight.append(PLEAT_WEIGHT)  # accordion pleat — leads
        self.hi, self.hj, self.hk, self.hl = map(np.array, (hi, hj, hk, hl))
        self.sign, self.mag = np.array(sign), np.array(mag)
        self.hinge_weight = np.array(weight)
        self.real_hinge = self.sign != 0

        # Edges (for the length constraint) and their flat rest lengths.
        self.ea = np.array([a for a, _ in edge_tris])
        self.eb = np.array([b for _, b in edge_tris])
        self.rest = np.linalg.norm(self.flat[self.eb] - self.flat[self.ea], axis=1)
        deg = np.zeros(self.V)
        np.add.at(deg, self.ea, 1.0)
        np.add.at(deg, self.eb, 1.0)
        self.inv_deg = 1.0 / np.maximum(deg, 1.0)

        # Hub cell pinned flat at the origin — the fixed centre everything wraps
        # around (and the free gauge choice for the solve).
        rho = np.maximum(np.abs(self.flat[:, 0]), np.abs(self.flat[:, 1]))
        self.pinned = rho <= HUB_HALF + 1e-9

        rings = max(pattern.ring_count, 1)
        self.cap = CAP
        # Clearance has to keep up with how tightly this preset wraps, which
        # scales with ring count via self.substeps below (see COLLISION_SEP_*).
        self.collision_sep = float(
            np.clip(
                COLLISION_SEP_BASE + COLLISION_SEP_PER_RING * rings,
                COLLISION_SEP_MIN,
                COLLISION_SEP_MAX,
            )
        )
        # The fold propagates outward from the pinned hub one ring at a time,
        # so more rings need more settling passes to converge (see SUBSTEPS_*
        # above). This is what keeps the big grids from stowing loose.
        self.substeps = int(
            np.clip(
                SUBSTEPS_BASE + SUBSTEPS_PER_RING * rings,
                SUBSTEPS_MIN,
                SUBSTEPS_MAX,
            )
        )

    # --- constraints -------------------------------------------------------
    def _dihedral(self, X):
        x1, x2, x3, x4 = X[self.hi], X[self.hj], X[self.hk], X[self.hl]
        e = x2 - x1
        Le = np.linalg.norm(e, axis=1, keepdims=True)
        n1 = np.cross(x2 - x1, x3 - x1)
        n2 = np.cross(x4 - x1, x2 - x1)
        L1 = np.linalg.norm(n1, axis=1, keepdims=True)
        L2 = np.linalg.norm(n2, axis=1, keepdims=True)
        n1u, n2u = n1 / np.maximum(L1, 1e-9), n2 / np.maximum(L2, 1e-9)
        h1, h2 = np.maximum(L1, 1e-9) / Le, np.maximum(L2, 1e-9) / Le
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

    def _project_dihedrals(self, X, frac):
        """Drive each hinge toward its target: real creases to their scheduled
        signed angle, facets toward flat — each scaled by its weight so the
        pleats and hub walls lead, the diagonal only aids, and cells stay
        rigid. Run last/hardest so the crease pattern dominates."""
        target = np.where(self.real_hinge, self.sign * self.mag * self.cap * frac, 0.0)
        w = np.ones(self.V)
        w[self.pinned] = 0.0
        w1, w2, w3, w4 = w[self.hi], w[self.hj], w[self.hk], w[self.hl]
        hw = self.hinge_weight
        for _ in range(DIHEDRAL_ITERS):
            th, g1, g2, g3, g4 = self._dihedral(X)
            err = np.mod(th - target + math.pi, 2 * math.pi) - math.pi
            err *= hw
            denom = (
                w1 * np.sum(g1 * g1, axis=1)
                + w2 * np.sum(g2 * g2, axis=1)
                + w3 * np.sum(g3 * g3, axis=1)
                + w4 * np.sum(g4 * g4, axis=1)
            )
            lam = err / np.maximum(denom, 1e-9)
            dX = np.zeros_like(X)
            cnt = np.zeros(self.V)
            for h, wh, g in ((self.hi, w1, g1), (self.hj, w2, g2), (self.hk, w3, g3), (self.hl, w4, g4)):
                np.add.at(dX, h, -(lam * wh)[:, None] * g)
                np.add.at(cnt, h, 1.0)
            dX /= np.maximum(cnt, 1.0)[:, None]
            dX[self.pinned] = 0.0
            X += dX

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

    def _collide(self, X):
        sep = self.collision_sep
        for _ in range(COLLISION_ITERS):
            pairs = cKDTree(X).query_pairs(sep, output_type="ndarray")
            if len(pairs) == 0:
                return
            i, j = pairs[:, 0], pairs[:, 1]
            flat_d = np.linalg.norm(self.flat[i, :2] - self.flat[j, :2], axis=1)
            far = flat_d > COLLISION_FLAT_EXCLUDE
            i, j = i[far], j[far]
            if len(i) == 0:
                return
            d = X[j] - X[i]
            dist = np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-6)
            push = np.maximum(sep - dist[:, 0], 0.0)[:, None] * (d / dist)
            F = np.zeros_like(X)
            np.add.at(F, i, -push)
            np.add.at(F, j, push)
            F[self.pinned] = 0.0
            X += F

    # --- sweep -------------------------------------------------------------
    @staticmethod
    def _smoothstep(u: float) -> float:
        u = min(max(u, 0.0), 1.0)
        return u * u * (3.0 - 2.0 * u)

    def solve_sweep(self):
        frames = [np.round(self.flat, 4).reshape(-1).tolist()]
        samples = [0.0]
        rng = np.random.default_rng(0)
        X = self.flat.copy()
        X[:, 2] += SEED_KICK * rng.standard_normal(self.V)
        X[self.pinned, 2] = 0.0
        for step in range(1, STEPS + 1):
            t = step / STEPS
            frac = self._smoothstep(t)
            # Settling is RAMPED, not uniform across the sweep: the pattern's
            # over-constraint only bites near full fold, so early (shallow)
            # frames converge with far fewer passes while the deep end — which
            # is what "100% folded" actually shows — gets the full budget.
            # Same final depth for roughly half the solve time as a flat count.
            n_sub = max(
                SUBSTEPS_RAMP_MIN,
                int(round(self.substeps * (SUBSTEPS_RAMP_FLOOR + (1.0 - SUBSTEPS_RAMP_FLOOR) * frac))),
            )
            for _ in range(n_sub):
                self._project_lengths(X)
                self._collide(X)
                self._project_dihedrals(X, frac)  # last → creases dominate
                X[self.pinned, 2] = 0.0
            frames.append(np.round(X, 4).reshape(-1).tolist())
            samples.append(t)
        return samples, frames


def solve_sweep(pattern: CreasePattern, params: FlasherParams):
    return FlasherFoldSolver(pattern, params).solve_sweep()
