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

# THE STOW MUST STAY FLAT. The flasher compresses radially into a low disc
# sitting just under the hub plane; it must not dome, cone, or grow into a
# tower as it folds. The gate used for every constant here: final-frame z-span
# within ~0.2 of the flat baseline, the rim (border vertices) staying level,
# and the radial z-profile flat from hub to rim. It is easy to wrap tighter by
# letting the model grow tall or dish in the middle — that is a regression,
# not progress, and it reads as obviously wrong next to real paper.

# How hard each preset is folded, and how it is settled, as a table keyed by
# ring count. These are NOT free parameters — each row sits at the measured
# limit of a DIFFERENT gate, and the binding gate changes with sheet size:
#
#   rings  preset  cap   sub  swirl   wrap   bound by
#   <=4    7x7     0.90    8   -0.8   0.488  facet flex (8.0 deg; only 3 rings
#                                            share the bending, so cells smear
#                                            before anything else gives)
#   5-8    15x15   0.97   12   -1.5   0.469  STRAIN (9.8%)
#   9-12   23x23   0.94   16   -1.5   0.545  STRAIN (9.9%)
#   >=13   31x31   0.92   24   -1.5   0.585  STRAIN (9.8%)
#   >=17   (none)  0.84   24   -1.5   0.693  STRAIN, for grids past any preset
#
# STRAIN IS NOW THE BINDING GATE ON EVERY GRID BUT THE SMALLEST, and ~10% mean
# is the line. It is not a cosmetic limit: pushing past it visibly CRUMPLES.
# Measured at 23x23 cap 1.0 / DIHEDRAL_ITERS 8 the wrap improves to 0.499 and
# every other metric still passes — rotation coherent, stow flat, zero phasing —
# but mean strain hits 11.1% and the rendered model comes out with a jagged rim
# and chewed-up facets. Wrap, height, phasing and even the twist profile all
# fail to catch that; only strain does. Do not trade strain for wrap here.
#
# CAP is the fraction of each crease's declared angle driven at foldness=1, and
# its ceiling is CRUMPLING, not self-intersection: past the limit the innermost
# ring starts turning AGAINST the wrap (measured on 23x23 at cap 1.0 / swirl
# -1.0: inner +8 deg while every outer ring is -17..-38) and within-ring spread
# doubles. How far it can go depends on SEED_SWIRL — a stronger swirl stabilises
# the spiral mode and buys real depth. 1.0 is a hard ceiling regardless, since
# _project_dihedrals wraps angles into (-180, 180] and a target past 180 deg
# aliases to a negative angle, folding the crease backward.
#
# SUBSTEPS (PBD settle passes per frame) scales up with ring count: the fold
# propagates outward from the pinned hub one ring at a time. More passes also
# LOWER strain, which is what lets the mid grids reach cap 1.0 at all. Bounded
# above by flatness — past these values the interior dishes and the stow grows.
#
# SEED_SWIRL is in radians of twist accumulated at the sheet edge over the whole
# fold (see below). Small sheets take less: over-swirling a 7x7 bends facets
# instead of turning rings.
#
# Rows are (min_rings, cap, substeps, swirl, layer_thickness), highest first.
FOLD_PROFILE = (
    (17, 0.84, 24, -1.5, 0.25),
    (13, 0.92, 24, -1.5, 0.25),
    (9, 0.94, 16, -1.5, 0.35),
    (5, 0.97, 12, -1.5, 0.35),
    (0, 0.90, 8, -0.8, 0.35),
)

DIHEDRAL_ITERS = 8  # dihedral projection iterations per substep (run last so
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

# --- self-collision: VERTEX-vs-TRIANGLE, not vertex-vs-vertex ---------------
# THIS IS WHAT LETS THE STOW BE BOTH TIGHT AND FLAT, and it is the reason the
# thickness below can be small. Stow height is roughly (layers stacked) x
# (layer thickness), so a flat stow needs THIN layers; but the old vertex-pair
# repulsion could only stop layers phasing by holding them a big distance
# apart (0.26-0.78), which is exactly what inflated the model into a tower
# when the fold was driven deep. Vertex-pair distance also structurally cannot
# catch the crossings that actually happen here: an edge passing through the
# middle of a facet with no two vertices ever close. Measured, a trailing
# vertex-pair pass only took 31x31 from 80 true intersections to 64.
#
# A real point-to-triangle test fixes both: it prevents penetration directly,
# so the thickness only has to be a true paper thickness rather than a safety
# shell, and thin layers keep the stow flat while the wrap pulls in tight.
# Layer thickness in grid units (cell = 1.0) — roughly half what the old
# vertex-pair repulsion needed for the same zero-phasing result, which is
# exactly why the stow comes out flatter. Thinner still on the largest grids,
# because they stack the most layers and height ~ layers x thickness; they can
# afford it because their higher substep count moves less per pass, so nothing
# tunnels through. Measured at 31x31/CAP=1.0/16 passes: 0.15 phases (228
# crossings), 0.20 and above are clean.
VT_ITERS = 6  # projection passes per call. NOT optional: a vertex buried in a
# tight stow gets many simultaneous contacts, and the per-vertex averaging
# below dilutes each one, so a couple of passes leaves crossings behind.
# Measured at 31x31 / thickness 0.35: 2 passes -> 4 intersections, 6 -> zero.
VT_FLAT_EXCLUDE = 1.6  # ignore triangles this close in the FLAT sheet — those
# are the vertex's own neighbourhood, which is meant to touch itself

SEED_KICK = 0.01  # tiny random z offset on the flat seed so the first fold
# step has a direction to break out of the perfectly-flat plane

# SEED_SWIRL — the sheet has TWO ways to get smaller, and without a nudge it
# picks the wrong one. It can spiral (every ring turning about the hub, the way
# a real flasher collapses) or it can just crush inward radially, which buckles
# the rings and reads as CRUMPLING. Both are near-symmetric solutions to the
# same constraints, so a random z seed leaves the choice to noise and the crush
# usually wins: measured twist per ring was +25 +16 +5 +2 -0 -2, i.e. the rim
# barely rotated at all while the inner rings buckled (spread 25 deg).
#
# Seeding a small COHERENT rotation, growing with radius, breaks that symmetry
# toward the spiral. It is only a seed — a few degrees on the flat sheet, which
# the length projection immediately cleans up — not a prescribed motion; the
# crease pattern still decides the final shape.
# Radians of twist accumulated at the sheet edge over the whole fold. Applied
# INCREMENTALLY as foldness advances, never all at once — the wrap winds up as
# the pleats close, the way real paper does, and frame 0 stays perfectly flat.
# Negative winds the sheet so that |rotation| GROWS outward, which is the
# real spiral: measured 23x23 twist per ring -13 -35 -42 -44 -46 -48. Positive
# instead spins the inner rings hardest (+44 +29 +20 ...), which is not a wrap.
# Bigger sheets get more, having more rings to wind. This also LOWERS strain
# (23x23: 7.45% -> 6.89%), confirming the spiral is the lower-energy mode the
# solver was previously failing to find rather than something forced on it.


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
        # Per-preset fold profile (see FOLD_PROFILE above).
        for min_rings, cap, subs, swirl, thick in FOLD_PROFILE:
            if rings >= min_rings:
                self.cap = cap
                self.substeps = subs
                self.swirl = swirl
                self.vt_thickness = thick
                break

        # Flat-space centroid of every face, used to skip a vertex's own
        # neighbourhood in the vertex-triangle test (those panels share creases
        # and are supposed to touch).
        self.face_flat_cent = self.flat[self.face_vids][:, :, :2].mean(axis=1)
        # A triangle's own extent, so the candidate search radius covers it.
        self.tri_reach = float(
            np.max(
                np.linalg.norm(
                    self.flat[self.face_vids][:, :, :2] - self.face_flat_cent[:, None, :],
                    axis=2,
                )
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

    @staticmethod
    def _closest_on_tri(p, a, b, c):
        """Closest point on triangle (a,b,c) to p, plus barycentric weights.

        Vectorised Ericson (Real-Time Collision Detection) region test: the
        closest point is on a vertex, an edge, or the face interior.
        """
        ab, ac, ap = b - a, c - a, p - a
        d1 = np.einsum("ij,ij->i", ab, ap)
        d2 = np.einsum("ij,ij->i", ac, ap)
        bp = p - b
        d3 = np.einsum("ij,ij->i", ab, bp)
        d4 = np.einsum("ij,ij->i", ac, bp)
        cp = p - c
        d5 = np.einsum("ij,ij->i", ab, cp)
        d6 = np.einsum("ij,ij->i", ac, cp)

        va = d3 * d6 - d5 * d4
        vb = d5 * d2 - d1 * d6
        vc = d1 * d4 - d3 * d2
        denom = np.where(np.abs(va + vb + vc) < 1e-12, 1e-12, va + vb + vc)
        v_f = vb / denom
        w_f = vc / denom

        # start from the face-interior solution, then override by region
        v = v_f
        w = w_f
        # vertex a
        m = (d1 <= 0) & (d2 <= 0)
        v = np.where(m, 0.0, v)
        w = np.where(m, 0.0, w)
        # vertex b
        m2 = (d3 >= 0) & (d4 <= d3)
        v = np.where(m2, 1.0, v)
        w = np.where(m2, 0.0, w)
        # vertex c
        m3 = (d6 >= 0) & (d5 <= d6)
        v = np.where(m3, 0.0, v)
        w = np.where(m3, 1.0, w)
        # edge ab
        m4 = (vc <= 0) & (d1 >= 0) & (d3 <= 0) & ~(m | m2 | m3)
        t_ab = d1 / np.where((d1 - d3) == 0, 1e-12, d1 - d3)
        v = np.where(m4, t_ab, v)
        w = np.where(m4, 0.0, w)
        # edge ac
        m5 = (vb <= 0) & (d2 >= 0) & (d6 <= 0) & ~(m | m2 | m3 | m4)
        t_ac = d2 / np.where((d2 - d6) == 0, 1e-12, d2 - d6)
        v = np.where(m5, 0.0, v)
        w = np.where(m5, t_ac, w)
        # edge bc
        m6 = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0) & ~(m | m2 | m3 | m4 | m5)
        t_bc = (d4 - d3) / np.where(
            ((d4 - d3) + (d5 - d6)) == 0, 1e-12, (d4 - d3) + (d5 - d6)
        )
        v = np.where(m6, 1.0 - t_bc, v)
        w = np.where(m6, t_bc, w)

        q = a + ab * v[:, None] + ac * w[:, None]
        return q, 1.0 - v - w, v, w

    def _collide_vt(self, X):
        """Push vertices out of triangles they are penetrating.

        Unlike vertex-pair repulsion this catches an edge/vertex passing
        through the middle of a facet, so the layer thickness can stay thin
        (which is what keeps the stow flat) without the sheet phasing.
        """
        h = self.vt_thickness
        for _ in range(VT_ITERS):
            tris = X[self.face_vids]
            cent = tris.mean(axis=1)
            # ALL triangles within reach, not the K nearest. A K-nearest search
            # fails exactly where it matters: on a fine grid the K closest
            # triangles to a vertex are all in its own flat neighbourhood (which
            # is excluded below), so the penetrating layer never gets tested.
            pairs = cKDTree(X).sparse_distance_matrix(
                cKDTree(cent), self.tri_reach + h, output_type="ndarray"
            )
            if len(pairs) == 0:
                return
            vi = pairs["i"].astype(np.intp)
            fi = pairs["j"].astype(np.intp)
            # skip the vertex's own neighbourhood in the FLAT sheet
            far_flat = (
                np.linalg.norm(self.flat[vi, :2] - self.face_flat_cent[fi], axis=1)
                > VT_FLAT_EXCLUDE
            )
            vi, fi = vi[far_flat], fi[far_flat]
            if len(vi) == 0:
                return
            a, b, c = X[self.face_vids[fi, 0]], X[self.face_vids[fi, 1]], X[self.face_vids[fi, 2]]
            p = X[vi]
            q, wa, wb, wc = self._closest_on_tri(p, a, b, c)
            d = p - q
            dist = np.linalg.norm(d, axis=1)
            hit = dist < h
            if not hit.any():
                return
            vi, fi = vi[hit], fi[hit]
            d, dist = d[hit], dist[hit]
            wa, wb, wc = wa[hit], wb[hit], wc[hit]
            # degenerate (vertex exactly on the facet): use the facet normal
            nrm = np.cross(b[hit] - a[hit], c[hit] - a[hit])
            nl = np.linalg.norm(nrm, axis=1, keepdims=True)
            n = np.where(
                dist[:, None] > 1e-9, d / np.maximum(dist, 1e-9)[:, None], nrm / np.maximum(nl, 1e-9)
            )
            pen = (h - dist)[:, None]
            # split the correction between the vertex and the facet
            corr = 0.5 * pen * n
            dX = np.zeros_like(X)
            cnt = np.zeros(self.V)
            np.add.at(dX, vi, corr)
            np.add.at(cnt, vi, 1.0)
            for col, wgt in ((0, wa), (1, wb), (2, wc)):
                tv = self.face_vids[fi, col]
                np.add.at(dX, tv, -corr * wgt[:, None])
                np.add.at(cnt, tv, 1.0)
            dX /= np.maximum(cnt, 1.0)[:, None]
            dX[self.pinned] = 0.0
            X += dX

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
        # Per-vertex swirl rate, applied INCREMENTALLY as the fold progresses
        # (see SEED_SWIRL). Applying it all at t=0 would snap the sheet into a
        # twist before it has begun folding; growing it with foldness is both
        # smooth and what the paper actually does — the wrap winds up as the
        # pleats close.
        ring = np.maximum(np.abs(self.flat[:, 0]), np.abs(self.flat[:, 1]))
        swirl_rate = self.swirl * (ring / max(ring.max(), 1e-9))
        swirl_rate[self.pinned] = 0.0
        prev_frac = 0.0
        for step in range(1, STEPS + 1):
            t = step / STEPS
            frac = self._smoothstep(t)
            if self.swirl:
                a = swirl_rate * (frac - prev_frac)
                ca, sa = np.cos(a), np.sin(a)
                x, y = X[:, 0].copy(), X[:, 1].copy()
                X[:, 0] = ca * x - sa * y
                X[:, 1] = sa * x + ca * y
            prev_frac = frac
            for _ in range(self.substeps):
                self._project_lengths(X)
                self._project_dihedrals(X, frac)  # creases dominate the shape
                self._collide_vt(X)  # ...but nothing is allowed to pass through
                X[self.pinned, 2] = 0.0
            frames.append(np.round(X, 4).reshape(-1).tolist())
            samples.append(t)
        return samples, frames


def solve_sweep(pattern: CreasePattern, params: FlasherParams):
    return FlasherFoldSolver(pattern, params).solve_sweep()
