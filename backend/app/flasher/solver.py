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
CAP = 0.68  # fraction of each crease's full declared angle driven at
# foldness=1. NOT 1.0 (a hard 180° flat-fold): this pattern is geometrically
# over-constrained near full fold (folding every crease to its full angle
# leaves a large loop-closure gap — measured ~30% of the sheet), so pushing
# to 180° forces the incompatibility out as edge STRETCHING (measured ~9%
# strain) and blunts the creases. Driving to ~0.68 instead reaches a crisp
# OPEN WAVE — pleats around 90-110°, the up/down corrugation the pattern is
# meant to make — with the creases folding 100% in their declared direction,
# strain down to ~5%, facets nearly flat (sharp creases), and no
# self-intersection. Raising it folds deeper but strains more and dulls the
# wave; lowering it is a shallower wave.

SUBSTEPS = 8  # PBD settle passes per frame
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
# Effective layer-separation ("paper thickness") scales down with ring count:
# a coarse preset stows into few chunky layers needing a big gap; a fine
# preset has many thin layers over a larger wrap and needs a small one.
COLLISION_SEP_AT_ZERO_RINGS = 0.78
COLLISION_SEP_PER_RING = 0.035
COLLISION_SEP_MIN = 0.2
COLLISION_SEP_MAX = 0.62

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
        self.collision_sep = float(
            np.clip(
                COLLISION_SEP_AT_ZERO_RINGS - COLLISION_SEP_PER_RING * rings,
                COLLISION_SEP_MIN,
                COLLISION_SEP_MAX,
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
        target = np.where(self.real_hinge, self.sign * self.mag * CAP * frac, 0.0)
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
            for _ in range(SUBSTEPS):
                self._project_lengths(X)
                self._collide(X)
                self._project_dihedrals(X, frac)  # last → creases dominate
                X[self.pinned, 2] = 0.0
            frames.append(np.round(X, 4).reshape(-1).tolist())
            samples.append(t)
        return samples, frames


def solve_sweep(pattern: CreasePattern, params: FlasherParams):
    return FlasherFoldSolver(pattern, params).solve_sweep()
