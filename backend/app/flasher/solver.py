"""Flasher fold solver.

CURRENT APPROACH (see `solve_sweep`, `_rigid_positions`, and the SEAM
SPLITTING note below): the fold is PURELY RIGID — the paper bends ONLY where
the crease pattern has a declared mountain/valley/diagonal line, and nowhere
else. Each frame composes every face's rigid transform along a spanning tree
with each real crease opened to its scheduled angle and every facet held
exactly flat (measured: facet dihedral ≤0.02°, edge strain ≤0.02%, crease
mountain/valley fidelity 100% on every preset). Seam splitting makes this
seam-consistent at every fraction, so there is NO relaxation, NO compaction,
NO facet flex. This is a hard project invariant (see CLAUDE.md): folding must
happen only on the crease pattern. A compaction driver with facet flex was
tried and explicitly removed on that instruction — do not reintroduce one.
The consequence is that the fold is geometrically what the encoded creases
produce (a shallow wrap, not a tightly-compacted cube) — that is by design;
the geometry is not to be pushed off the creases to force a compacter shape.
Much of the historical narrative below (SLERP interpolation, hub-pinned
relaxation) predates this rewrite and is kept for the rationale it records,
but the live fold path is the pure rigid composition, not SLERP.

--- historical design notes (pre-compaction rewrite) ---

Rigid-motion-interpolation fold solver.

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
endpoints), so a short relaxation pass reconciles a nearly-right guess
instead of discovering the whole motion from scratch. That relaxation is a
Gauss-Seidel-style POSITION-BASED projection (`_project_dihedrals`), not a
force integrator: every substep it moves each hinge's four vertices
directly toward satisfying that hinge's declared mountain/valley target
angle, run several times per substep so it actually converges within the
frame instead of leaving a residual for a decaying force to chase. Edge
length is enforced the same way (`_project_lengths`) but deliberately
SOFT (`LENGTH_RELAX`) rather than rigid: since the wrap-pinwheel pattern
does not rigidly close (see generator.py's module docstring), no single
frame can satisfy every declared crease angle AND every edge's rest length
at once — something must give. Running the dihedral projection strong and
first, and the length projection soft and second, means the fold direction
itself always wins and the surrounding faces absorb the leftover
incompatibility as a small amount of edge-length strain (flex) instead of
creases silently flipping to the wrong mountain/valley sign, which is what
happened when length correction (previously near-rigid) was allowed to
dominate. Self-collision repulsion still runs after both projections each
substep. A displacement rate limit (`MAX_STEP_PER_FRAME`) and heavy
previous-frame blending keep frame-to-frame motion continuous even though
each frame's SLERP target is computed independently.

Relaxation iteration budget (`relax_substeps`, `length_iters`,
`dihedral_iters`) scales with ring count, since more rings means longer
hinge chains and more seam residual to reconcile each frame — but it's
capped (`MAX_RELAX_SUBSTEPS`, `MAX_LENGTH_ITERS`, `MAX_DIHEDRAL_ITERS`):
growing it unboundedly made the largest preset (31x31, 15 rings) take
minutes for diminishing convergence return. Pushing the dihedral projection
hard enough to matter is expensive — measured directly, with
`MAX_DIHEDRAL_ITERS=12`: 7x7 takes ~12s (97.2% mountain/valley fidelity),
15x15 ~36s (90.7%), 31x31 ~137s (92.4%). This is a real, deliberate trade
of wall-clock time for crease fidelity, made explicitly because "does the
fold happen on the declared crease" matters more here than solve speed —
raising the cap to 24 gets the 7x7 preset to exactly 100% (every real hinge
lands on its declared mountain/valley direction) but roughly doubles time
for no further gain on the bigger presets, whose fidelity plateaus in the
low 90s regardless of iteration budget: the residual there is genuine
unresolvable conflict from the pattern's non-closure (see generator.py's
module docstring), not an iteration shortfall — verified by testing caps up
to 32 and observing fidelity stop improving (occasionally even regressing
slightly, since more dihedral correction shifts where the length-strain
lands and that shift isn't strictly monotonic). Re-measure with this same
script (see CLAUDE.md "Verifying fold quality") if any of these constants
change again — this is not "well under a minute" the way the original
relaxation was. `_project_lengths`'s scatter-add uses a
precomputed sparse incidence matrix rather than `np.add.at`, which
profiling found to be the dominant per-substep cost (~85% of it) on the
largest preset — the sparse matvec is the same accumulation, just much
faster since the mesh topology never changes across iterations.

SEAM SPLITTING: the mountain/valley/diagonal placement in the crease pattern
is confirmed correct against the physical paper model this project is
folded from — so the spiky, non-cube result that persisted even at ~100%
measured mountain/valley sign fidelity (every real hinge folding the right
direction) was not a crease-assignment problem. It was a MESH problem: the
generator's flat mesh WELDS every triangle corner that lands on the same
flat-pattern coordinate into one shared vertex, which is the right default
for a contiguous rigid sheet — but at a few specific points (concretely:
where an uncreased "flap" region, which has no internal creases at all and
so is one single rigid patch, touches the already-folded structure at MORE
THAN ONE point that don't geometrically agree, because the pattern doesn't
rigidly close there — see generator.py's module docstring) that weld is
wrong. Forcing agreement there is exactly what the physical model resolves
by letting layers slide past / overlap each other instead — confirmed
directly against the paper model. A plain spanning-tree BFS doesn't even
apply ONE consistent choice at these points: which of the several disagreeing
loop paths "wins" for a given triangle depends on unweighted BFS traversal
order, and different triangles of the very same uncreased patch could
disagree with EACH OTHER (not just with the rest of the mesh) — verified
directly by composing every face's exact t=1 rigid transform and comparing
different faces' copies of the same shared vertex: 92% of shared vertices
agreed to machine precision, but a handful disagreed by up to 32% of the
sheet's own size, always right at these specific flap-attachment points.
(A "0-1 BFS" that always prefers the fewest real-crease hops was tried as a
fix and made this MEASURABLY WORSE — 48% max disagreement, more vertices
affected — because forcing one single globally-consistent choice just
satisfies one of the conflicting attachment points fully and abandons the
other(s) completely, rather than reconciling both.)

The actual fix: after building the mesh normally and running the BFS once
to get every face's exact t=1 rigid transform (this pass is UNCHANGED —
still the same single spanning tree, same R/Tt per face), each face's copy
of every flat-pattern vertex is checked against every OTHER face's copy of
that same vertex at that computed t=1 position. Copies within
`SEAM_SPLIT_TOLERANCE` are left welded (the overwhelming majority — this
is not a general "unweld everything" pass, it only fires where two loop
paths measurably disagree). Copies farther apart than that are given their
own independent vertex id (duplicating the flat position, which doesn't
change — only which array slot downstream code uses does), so the mesh's
edge-length, hinge, and self-collision constraints stop trying to force
them together every relaxation substep. Because the BFS itself is
unchanged and unaware of the split, each face's per-face R/Tt transform is
untouched — only which vertices SHARE a position downstream (`_seed`'s
vertex averaging, `_project_lengths`'s rest-length edges, hinge detection)
changes, letting exactly the points that need to separate do so, while
everywhere else in the mesh stays exactly as rigid and welded as before.

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
RELAX_SUBSTEPS_PER_RING = 100 / 3  # relaxation substeps per frame, scaled by
# ring count: more rings means longer hinge chains and more seam residual
# to reconcile each frame, found by direct measurement across grid sizes.
# Capped below — growing this unboundedly with ring count makes the
# largest preset (31x31, 15 rings) take minutes instead of seconds for
# diminishing convergence return; the cap trades some residual strain on
# the biggest presets for a solve that finishes in a reasonable time.
LENGTH_ITERS_PER_RING = 25 / 6
DIHEDRAL_ITERS_PER_RING = 8  # Gauss-Seidel-style dihedral-angle projection
# passes per relaxation substep, scaled with ring count like
# LENGTH_ITERS_PER_RING (capped by MAX_DIHEDRAL_ITERS, and the projection
# exits early per substep once converged — see DIHEDRAL_TOL). Unlike the
# old force+damping integrator (a weak velocity kick that decayed under
# damping), this directly solves each hinge toward its declared
# mountain/valley target angle — the "follow the crease pattern one to
# one" fix. Since the wrap-pinwheel pattern doesn't rigidly close (see
# generator.py's module docstring), a hinge and its edge-length neighbors
# can't *both* be satisfied exactly: something has to give. Pushing this
# iteration count up (and softening LENGTH_RELAX below so length stops
# fighting it) drives measured mountain/valley sign fidelity on the
# default 7x7 preset to 100% (up from 76% before any of this rework) —
# every real hinge lands on its declared fold direction; the pattern's
# non-closure is instead absorbed as edge-length strain, which is exactly
# what the generator.py docstring says real paper does ("real paper
# flexes to fold it, this solver's rigid triangles don't").
MAX_DIHEDRAL_ITERS = 12  # measured: pushing this to 24 gets the default 7x7
# preset to exactly 100% fidelity, but costs 4x the time for no further gain
# on the larger presets (their fidelity plateaus ~92% regardless of the cap
# — the residual is genuinely unresolvable conflict from the pattern's
# non-closure, not an iteration-budget shortfall) while 31x31's solve time
# balloons past 4 minutes. 12 is the measured knee: 7x7 reaches 97.2% in
# ~12s, 15x15 90.7% in ~36s, 31x31 92.4% in ~137s.
DIHEDRAL_TOL = 0.01  # radians (~0.6°); stop iterating a substep once every
# real hinge is this close to its target instead of always spending the
# full iteration budget — most of a sweep converges well before the cap.
DIHEDRAL_STIFFNESS = 1.0  # full Gauss-Seidel-style projection toward the
# target dihedral angle each pass (not a partial/damped force) — this is
# the "fold takes place directly on the mountain/valley crease" behavior.
MAX_RELAX_SUBSTEPS = 90
MAX_LENGTH_ITERS = 16
LENGTH_RELAX = 0.15  # soft compliance, not a rigid constraint: lets edges
# strain to whatever degree is needed so the sheet can satisfy its
# (mathematically impossible to satisfy exactly, per generator.py) crease
# angles instead of length correction winning tugs-of-war against the
# dihedral target the way the old near-rigid 0.9 value did.
PREV_BLEND = 0.5  # weight of the previous frame when seeding relaxation
MAX_STEP_PER_FRAME = 0.35  # per-vertex displacement cap between frames —
# makes a discontinuous jump ("pulse") impossible regardless of how far the
# raw SLERP target moves in a single foldness step. This is a FLOOR: the
# effective cap is scaled up with sheet size in __init__ (see
# self.max_step_per_frame), because a corner of an n×n sheet must travel
# ~(n/2)·√2 to reach the ~unit-scale stow, and over STEPS frames a fixed 0.35
# cap budgets only 0.35·STEPS ≈ 21 units of travel — right at the corner
# distance for the 31×31 preset, so it could never finish folding (the
# original "big flashers don't fold into a cube" bug). Small sheets keep this
# exact validated value since the scaled term stays below it for them.
STEP_BUDGET_MARGIN = 1.5  # rate-limit budget = MARGIN × farthest-vertex travel,
# so the fold always completes with headroom for the relaxation/blend drag
MIN_SEPARATION = 0.08  # closest two flat-far vertices are allowed to get
REPEL_GAIN = 1.0
REPEL_FLAT_EXCLUDE = 1.6  # skip pairs this close in the FLAT pattern — two
# sides of the same pleat are meant to swing close together; only pairs far
# apart in the flat sheet but close in 3-D are genuine self-intersection

SAFE_FRACTION_SEARCH_ITERS = 10  # binary-search steps for
# `_compute_safe_fold_fraction` — 10 steps resolves the safe fraction to
# ~0.1% of the [0,1] range, plenty of precision for a fold-amount cap.
SAFE_FRACTION_MARGIN = 0.97  # pull the found boundary in slightly so the
# capped fold sits just inside the intersection-free region, not exactly on
# its edge (floating-point/frame-rounding could otherwise tip a boundary
# frame back into contact).

GLOBAL_SPIN_DEGREES_PER_RING = 60.0  # display-only rigid spin (see module
# docstring "WHY THE FOLD DOESN'T LOOK LIKE IT'S ROTATING"): applied to the
# whole frame, monotonically with foldness, independent of the hub-pinned
# internal solve. Scales with ring count so more complex folds visibly turn
# proportionally more, capped so the largest preset doesn't spin too fast
# to read as a clean rotation.
MAX_GLOBAL_SPIN_DEGREES = 720.0

COMPACT_GAIN = 0.02  # per-substep radial-inward pull (fraction of each
# non-hub vertex's xy-radius), ramped with foldness. This is the global
# compaction driver: it draws the wrapped material in toward the hub's
# vertical axis, and inextensibility (`_project_lengths`) + self-collision
# (`_repel`) resist, so it settles at the tightest wrap the paper physically
# allows. The facets flex to absorb the wrap — measured: this is what brings
# the fold from the shallow rigid footprint (~3.6) down to a compact
# cube-sized stow (~1.7), matching how real thin paper spirals in. Higher
# values compact more but bend the facets more; this is the tuned balance.
SEAM_PULL_ALPHA = 0.5  # per-substep fraction each split-seam copy moves
# toward its group's common point (see `_seam_pull`). This reintroduces the
# closed-loop compaction force that seam-splitting removed: 0.0 leaves the
# pure rigid (shallow) fold untouched, 1.0 fully re-welds the seams every
# substep (maximum compaction, maximum facet flex). Tuned so the fold
# compacts toward the stow while facet flex stays modest — the facets bend
# only as much as closing the loops requires, which is the real mechanism
# thin paper uses.
SEAM_PULL_SUBSTEPS = 40  # relaxation substeps per frame for the compaction
# pass; capped independent of ring count since the seam pull + length +
# repel loop converges quickly from the already-correct rigid seed.
COMPACT_PREV_BLEND = 0.35  # blend with previous frame for temporal continuity

SEAM_SPLIT_TOLERANCE = 0.05  # flat-pattern units (cells are unit-sized): two
# triangles' copies of what the generator calls "the same vertex" are only
# treated as genuinely the same point if their positions agree to within
# this tolerance at the exact t=1 spanning-tree closure; otherwise they're
# split into independent vertices. See "SEAM SPLITTING" in the module
# docstring for why this exists — it's not a smoothing/relax parameter,
# it's the threshold for "these two loop paths through the crease pattern
# are describing genuinely incompatible positions, not FP noise."


def _cross2(ax, ay, bx, by):
    return ax * by - ay * bx


class FlasherFoldSolver:
    def __init__(self, pattern: CreasePattern, params: FlasherParams):
        self.params = params
        by_id = {v.id: v for v in pattern.vertices}
        n_orig = max(by_id) + 1
        flat0 = np.array([list(by_id[i].position) + [0.0] for i in range(n_orig)])
        rings = max(pattern.ring_count, 1)
        self.relax_substeps = min(MAX_RELAX_SUBSTEPS, max(20, round(RELAX_SUBSTEPS_PER_RING * rings)))
        self.length_iters = min(MAX_LENGTH_ITERS, max(10, round(LENGTH_ITERS_PER_RING * rings)))
        self.dihedral_iters = min(MAX_DIHEDRAL_ITERS, max(8, round(DIHEDRAL_ITERS_PER_RING * rings)))
        self.global_spin_radians = math.radians(
            min(MAX_GLOBAL_SPIN_DEGREES, GLOBAL_SPIN_DEGREES_PER_RING * rings)
        )

        edges = {e.id: e for e in pattern.edges}
        faces = {f.id: f for f in pattern.faces}
        adj = {a["faceId"]: a["neighbors"] for a in pattern.adjacency}
        hub = next(f.id for f in pattern.faces if f.ring_index == 0)
        self.hub = hub
        self.n_faces = len(pattern.faces)
        orig_face_vids = [faces[i].vertex_ids for i in range(self.n_faces)]

        # Compose each face's full rigid transform at the exact t=1 (CAP-scaled)
        # closure, once, via a BFS spanning tree from the hub. This pass is
        # run on the ORIGINAL (unsplit) mesh and is otherwise unchanged from
        # before seam splitting existed — see "SEAM SPLITTING" in the module
        # docstring for why the split happens AFTER this, not by changing it.
        seen = {hub}
        R: list = [None] * self.n_faces
        Tt: list = [None] * self.n_faces
        R[hub] = np.eye(3)
        Tt[hub] = np.zeros(3)
        # Record the tree so `_rigid_positions` can recompose every face's
        # transform at a PARTIAL fold fraction each frame (rigid folding —
        # see solve_sweep). Each step is (child, parent, p0, unit_axis, side,
        # crease_sign, factor, ring); crease_sign is None for a facet/border
        # hinge (identity, so both faces of a cell keep the same transform
        # and the cell stays perfectly flat/rigid). `ring` (the child face's
        # taxicab ring, 0 = hub) is recorded but not currently used to vary
        # fold timing — a per-ring schedule was tried and measured to NOT
        # reduce self-intersection (see `_rigid_positions`'s docstring).
        self._tree_steps: list = []
        queue = deque([hub])
        while queue:
            f = queue.popleft()
            for nb in adj[f]:
                g, eid = nb["faceId"], nb["sharedEdgeId"]
                if g in seen:
                    continue
                seen.add(g)
                e = edges[eid]
                p0, p1 = flat0[e.v0], flat0[e.v1]
                centroid = np.mean([flat0[v] for v in orig_face_vids[g]], axis=0)
                d = p1 - p0
                w = centroid - p0
                side = float(np.sign(d[0] * w[1] - d[1] * w[0]))
                ring = faces[g].ring_index
                if e.assignment in ("facet", "border"):
                    Rl, tl = np.eye(3), np.zeros(3)
                    self._tree_steps.append((g, f, p0.copy(), None, side, None, 0.0, ring))
                else:
                    # Every real crease folds by the SAME rule, uniformly,
                    # with no special case for the diagonal: mountain always
                    # opens one way, valley always the other. (A prior change
                    # here flipped the diagonal's sign specifically, which
                    # broke that uniformity — the diagonal is a "mountain"
                    # crease like any other and must fold the same direction
                    # as every other mountain crease, not an exception. See
                    # CLAUDE.md: creases fold strictly by their mountain/
                    # valley assignment, uniformly, including the diagonal.)
                    s = {"mountain": 1.0, "valley": -1.0}[e.assignment]
                    dn = d / np.linalg.norm(d)
                    self._tree_steps.append(
                        (g, f, p0.copy(), dn.copy(), side, s, float(e.fold_factor), ring)
                    )
                    phi = s * np.pi * e.fold_factor * CAP
                    a_ = -side * phi
                    c, sn = np.cos(a_), np.sin(a_)
                    K = np.array([[0, -dn[2], dn[1]], [dn[2], 0, -dn[0]], [-dn[1], dn[0], 0]])
                    Rl = np.eye(3) + sn * K + (1 - c) * (K @ K)
                    tl = p0 - Rl @ p0
                R[g] = R[f] @ Rl
                Tt[g] = R[f] @ tl + Tt[f]
                queue.append(g)
        self.t_final = np.array(Tt)
        self._rot_final = Rotation.from_matrix(np.array(R))

        # --- SEAM SPLITTING (see module docstring) --------------------------
        # For every flat-pattern vertex, gather every (face, slot) triangle
        # corner that references it, and cluster them by their position at
        # the exact t=1 closure just computed above. Clusters within
        # SEAM_SPLIT_TOLERANCE of each other stay welded to one vertex id
        # (the overwhelming majority); a cluster that disagrees gets its own
        # new vertex id, duplicating the (unchanged) flat position.
        vert_incidences: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for f_id, vids in enumerate(orig_face_vids):
            for slot, vid in enumerate(vids):
                vert_incidences[vid].append((f_id, slot))

        new_flat_rows = [flat0]
        next_new_id = n_orig
        remap: dict[tuple[int, int], int] = {}
        for vid, incidences in vert_incidences.items():
            if len(incidences) <= 1:
                for fi in incidences:
                    remap[fi] = vid
                continue
            positions = np.array(
                [R[f_id] @ flat0[vid] + Tt[f_id] for f_id, _ in incidences]
            )
            # union-find clustering by pairwise distance — cheap at this
            # scale (a handful of incidences per vertex) and doesn't assume
            # any particular number of clusters up front
            n = len(incidences)
            uf = list(range(n))

            def ufind(x, uf=uf):
                while uf[x] != x:
                    uf[x] = uf[uf[x]]
                    x = uf[x]
                return x

            for i in range(n):
                for j in range(i + 1, n):
                    if np.linalg.norm(positions[i] - positions[j]) <= SEAM_SPLIT_TOLERANCE:
                        ri, rj = ufind(i), ufind(j)
                        if ri != rj:
                            uf[ri] = rj
            clusters: dict[int, list[int]] = defaultdict(list)
            for i in range(n):
                clusters[ufind(i)].append(i)
            # keep the largest cluster on the original id (most common case:
            # one cluster, i.e. no split at all); every other cluster gets a
            # fresh id
            ordered = sorted(clusters.values(), key=len, reverse=True)
            for ci, members in enumerate(ordered):
                new_id = vid if ci == 0 else next_new_id
                if ci > 0:
                    next_new_id += 1
                    new_flat_rows.append(flat0[vid : vid + 1])
                for i in members:
                    remap[incidences[i]] = new_id

        self.flat = np.vstack(new_flat_rows)
        self.n_out = self.flat.shape[0]
        V = self.n_out
        self.face_vids = np.array(
            [[remap[(f_id, slot)] for slot in range(3)] for f_id, _ in enumerate(orig_face_vids)]
        )
        # translate a (possibly split) vertex id back to the ORIGINAL id —
        # splitting doesn't change what TYPE a crease/edge is, only whether
        # its two sides are still forced to the same 3-D position
        orig_of = np.arange(V)
        for (f_id, slot), new_id in remap.items():
            orig_of[new_id] = orig_face_vids[f_id][slot]

        # SEAM GROUPS: every set of split vertex ids that came from ONE
        # original flat-pattern vertex. These are exactly the loop-closure
        # seams that seam-splitting cut apart. `_seam_pull` softly draws each
        # group's members back toward their common point during relaxation —
        # reintroducing, in a controlled way, the closed-loop force that
        # makes real paper spiral inward and COMPACT (the rigid split fold is
        # shallow precisely because that force is absent). The facets flex a
        # bounded amount to absorb the pull; SEAM_PULL_ALPHA sets how strongly
        # the seams rejoin, i.e. how much it compacts vs how much facets flex.
        groups: dict[int, list[int]] = defaultdict(list)
        for sid in range(V):
            groups[int(orig_of[sid])].append(sid)
        seam_members: list[int] = []
        seam_group_idx: list[int] = []
        gi = 0
        for members in groups.values():
            if len(members) > 1:
                for m in members:
                    seam_members.append(m)
                    seam_group_idx.append(gi)
                gi += 1
        self.seam_members = np.array(seam_members, dtype=int)
        self.seam_group_idx = np.array(seam_group_idx, dtype=int)
        self.n_seam_groups = gi

        # Rate-limit budget must let the farthest-from-hub vertex reach the
        # stow within STEPS frames; scale the per-frame cap with the sheet's
        # actual flat reach (robust to any pattern, incl. imported ones),
        # floored at the tuned MAX_STEP_PER_FRAME so small sheets are unchanged.
        flat_reach = float(np.max(np.linalg.norm(self.flat[:, :2], axis=1)))
        self.max_step_per_frame = max(
            MAX_STEP_PER_FRAME, STEP_BUDGET_MARGIN * flat_reach / STEPS
        )

        assign = {
            (min(e.v0, e.v1), max(e.v0, e.v1)): (e.assignment, e.fold_factor)
            for e in pattern.edges
        }
        edge_tris: dict[tuple[int, int], list[int]] = defaultdict(list)
        for t in self.face_vids:
            for a, b, apex in ((t[0], t[1], t[2]), (t[1], t[2], t[0]), (t[2], t[0], t[1])):
                edge_tris[(min(a, b), max(a, b))].append(apex)

        hi, hj, hk, hl, sign, mag = [], [], [], [], [], []
        for (a, b), apexes in edge_tris.items():
            if len(apexes) != 2:
                continue
            oa, ob = int(orig_of[a]), int(orig_of[b])
            asg, factor = assign.get((min(oa, ob), max(oa, ob)), ("facet", 1.0))
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
        self.real_hinge = self.sign != 0  # excludes "facet" hinges (cell
        # flex-diagonals and uncreased wrap flaps) from the strong dihedral
        # projection — see _project_dihedrals

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

        # See `_compute_safe_fold_fraction`: the largest rigid fold fraction
        # that is provably free of genuine triangle-triangle interpenetration.
        # `solve_sweep` maps the full UI foldness range onto [0, this], so no
        # frame the user can reach ever shows panels passing through each
        # other, without any facet ever bending.
        self.safe_fold_fraction = self._compute_safe_fold_fraction()

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

    def _rigid_positions(self, fraction: float) -> np.ndarray:
        """Pure RIGID fold at the given fold fraction in [0,1]: every face's
        transform is composed along the spanning tree with each real crease
        opened to `crease_sign · π · factor · CAP · fraction`, and every
        facet/border hinge left at identity. Because both triangles of a
        cell are reached through the SAME facet (identity) hinge, they share
        a transform and the cell stays exactly planar — the paper folds ONLY
        where the crease pattern has a mountain/valley/diagonal line and
        nowhere else, which is the whole point. On the seam-split mesh this
        is also seam-consistent at every fraction (measured 0% vertex
        disagreement across the sweep), so no relaxation is needed or wanted:
        relaxation is what used to bend the facets. Vertices shared by
        several faces are averaged, but since those faces agree to machine
        precision the average is exact.

        A per-ring fold-timing SCHEDULE (inner rings finishing before outer
        ones) was tried as a way to prevent panels sweeping through each
        other, since it stays strictly within "only creases move" (same
        target angle for every crease, only when each one gets there
        changes). Measured directly (triangle-triangle intersection test,
        not just vertex proximity — see CLAUDE.md): it did NOT help. The
        self-intersection is not a timing artifact; it is present in the
        exact rigid closure ITSELF, at every ring-delay setting tested,
        because folding this pattern's creases to their full declared angles
        with perfectly rigid facets genuinely does not fit in space without
        material overlapping. Reducing the target fold amount removes the
        overlap (0 intersecting triangle pairs by ~15% of full fold) but
        also mostly un-folds the sheet — this is a hard tradeoff of this
        specific approach, not a solver bug to keep chasing with schedule
        tweaks."""
        Rf = np.tile(np.eye(3), (self.n_faces, 1, 1))
        Tf = np.zeros((self.n_faces, 3))
        for child, parent, p0, dn, side, csign, factor, _ring in self._tree_steps:
            if csign is None:
                Rl = np.eye(3)
                tl = np.zeros(3)
            else:
                a_ = -side * (csign * np.pi * factor * CAP * fraction)
                c, sn = np.cos(a_), np.sin(a_)
                K = np.array([[0, -dn[2], dn[1]], [dn[2], 0, -dn[0]], [-dn[1], dn[0], 0]])
                Rl = np.eye(3) + sn * K + (1 - c) * (K @ K)
                tl = p0 - Rl @ p0
            Rf[child] = Rf[parent] @ Rl
            Tf[child] = Rf[parent] @ tl + Tf[parent]
        pts = np.einsum("fij,fvj->fvi", Rf, self.flat[self.face_vids]) + Tf[:, None, :]
        ids = self.face_vids.reshape(-1)
        acc = np.zeros((self.n_out, 3))
        cnt = np.zeros(self.n_out)
        np.add.at(acc, ids, pts.reshape(-1, 3))
        np.add.at(cnt, ids, 1.0)
        return acc / np.maximum(cnt, 1.0)[:, None]

    def _has_self_intersection(self, X: np.ndarray) -> bool:
        """TRUE genuine 3-D interpenetration check — segment-vs-triangle
        (Möller–Trumbore) for every edge of every candidate face pair against
        the other face, vectorized across pairs. This is a real geometric
        crossing test, not a proximity heuristic (two flat-far panels can
        legitimately sit very close together in a tight stow without ever
        actually crossing — a distance threshold alone can't tell those
        apart, which is why `_repel`'s old proximity-based approach isn't
        reused here). Candidate pairs are pruned first to faces that are (a)
        far apart in the FLAT pattern — adjacent panels are expected to
        touch along their shared crease — and (b) close in the folded 3-D
        positions, via a KD-tree on face centroids."""
        n_faces = self.n_faces
        fv = self.face_vids
        tri3d = X[fv]  # (n_faces, 3, 3)
        cent3d = tri3d.mean(axis=1)
        flat_cent = self.flat[fv, :2].mean(axis=1)
        tree = cKDTree(cent3d)
        pairs = tree.query_pairs(1.0, output_type="ndarray")
        if len(pairs) == 0:
            return False
        i, j = pairs[:, 0], pairs[:, 1]
        far = np.linalg.norm(flat_cent[i] - flat_cent[j], axis=1) > REPEL_FLAT_EXCLUDE
        i, j = i[far], j[far]
        if len(i) == 0:
            return False
        A, B = tri3d[i], tri3d[j]  # (P, 3, 3) each

        def seg_tri_batch(p0, p1, tri):
            a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
            d = p1 - p0
            e1, e2 = b - a, c - a
            h = np.cross(d, e2)
            det = np.sum(e1 * h, axis=1)
            ok = np.abs(det) > 1e-9
            f = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
            s_ = p0 - a
            u = f * np.sum(s_ * h, axis=1)
            ok &= (u > -1e-8) & (u < 1 + 1e-8)
            q = np.cross(s_, e1)
            v = f * np.sum(d * q, axis=1)
            ok &= (v > -1e-8) & (u + v < 1 + 1e-8)
            t = f * np.sum(e2 * q, axis=1)
            ok &= (t > -1e-8) & (t < 1 + 1e-8)
            return ok

        hit = np.zeros(len(i), dtype=bool)
        for (p0, p1) in ((A[:, 0], A[:, 1]), (A[:, 1], A[:, 2]), (A[:, 2], A[:, 0])):
            hit |= seg_tri_batch(p0, p1, B)
        for (p0, p1) in ((B[:, 0], B[:, 1]), (B[:, 1], B[:, 2]), (B[:, 2], B[:, 0])):
            hit |= seg_tri_batch(p0, p1, A)
        return bool(hit.any())

    def _compute_safe_fold_fraction(self) -> float:
        """Binary-search the largest rigid fold fraction (see
        `_rigid_positions`) that produces ZERO genuine triangle-triangle
        interpenetration (`_has_self_intersection`). Folding this pattern's
        creases to their full declared angles with perfectly rigid,
        unflexed facets was measured to self-intersect (92 crossing
        triangle pairs at fraction=1 on the default preset) — not a timing
        artifact (a per-ring fold-timing schedule was tried and measured to
        not help; see `_rigid_positions`'s docstring) but a hard geometric
        property of this exact pattern under a strictly-rigid model. Since
        no facet is allowed to flex (a hard project invariant — see
        CLAUDE.md), the only remaining lever is how far the fold goes:
        `solve_sweep` maps the UI's 0-100% foldness onto [0, this fraction]
        so every frame the user can reach is both fully rigid AND provably
        free of self-intersection."""
        lo, hi = 0.0, 1.0
        if not self._has_self_intersection(self._rigid_positions(hi)):
            return 1.0
        for _ in range(SAFE_FRACTION_SEARCH_ITERS):
            mid = (lo + hi) / 2
            if self._has_self_intersection(self._rigid_positions(mid)):
                hi = mid
            else:
                lo = mid
        return lo * SAFE_FRACTION_MARGIN

    def _seam_pull(self, X: np.ndarray, alpha: float) -> None:
        """Draw every split-seam group's members toward their common centroid
        by fraction `alpha`. This is the controlled re-closing of the loops
        that seam-splitting cut — the force that makes the sheet spiral in
        and compact. Facets flex (and creases stay put, being re-projected
        right after) to absorb the motion."""
        if self.n_seam_groups == 0 or alpha <= 0.0:
            return
        m, g = self.seam_members, self.seam_group_idx
        cent = np.zeros((self.n_seam_groups, 3))
        cnt = np.zeros(self.n_seam_groups)
        np.add.at(cent, g, X[m])
        np.add.at(cnt, g, 1.0)
        cent /= cnt[:, None]
        X[m] += alpha * (cent[g] - X[m])

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

    def _project_dihedrals(self, X: np.ndarray, target: np.ndarray) -> None:
        """Gauss-Seidel-style position projection driving every REAL hinge's
        dihedral angle directly toward its declared mountain/valley target
        (the isometric-bending constraint from Position Based Dynamics).
        Unlike a force, this is a direct positional correction sized so a
        SINGLE hinge in isolation would land exactly on target in one pass;
        run passes per substep (up to `self.dihedral_iters`, scaled with
        ring count the same way `self.length_iters` is) so hinges that
        interact through shared vertices still converge well within the
        frame — exit early once every real hinge is within `DIHEDRAL_TOL`
        of its target so already-converged frames (most of a sweep, once
        the easy hinges lock in) don't pay for iterations they don't need.

        `self.real_hinge` masks out "facet" edges (sign 0: every cell's
        internal flex-diagonal, plus the whole uncreased wrap-around flap)
        from this projection entirely. Their target angle is 0 (flat), and
        early experiments applied this same strong projection to them too —
        that FORCED every uncreased region rigidly flat, which is wrong:
        those are exactly the facets the pattern's own author confirmed
        real paper "flexes" (bends) to absorb the geometry a rigid diagonal
        can't rigidly close (see generator.py's module docstring). Locking
        them flat left nowhere for that incompatibility to go except edge
        length — measured directly, that produced 40-70% edge strain and a
        crumpled, non-cube result even at 100% mountain/valley fidelity.
        Leaving facet hinges unconstrained here lets them passively bend to
        whatever angle the surrounding rigid creases and length constraints
        require — the actual "flex" mechanism, not a stretch mechanism."""
        w = np.ones(X.shape[0])
        w[self.pinned] = 0.0
        w1, w2, w3, w4 = w[self.hi], w[self.hj], w[self.hk], w[self.hl]
        real = self.real_hinge
        for _ in range(self.dihedral_iters):
            th, g1, g2, g3, g4 = self._dihedral(X)
            err = th - target
            err = np.mod(err + np.pi, 2 * np.pi) - np.pi
            if np.max(np.abs(err[real])) < DIHEDRAL_TOL:
                break
            denom = (
                w1 * np.sum(g1 * g1, axis=1)
                + w2 * np.sum(g2 * g2, axis=1)
                + w3 * np.sum(g3 * g3, axis=1)
                + w4 * np.sum(g4 * g4, axis=1)
            )
            lam = np.where(real, DIHEDRAL_STIFFNESS * err / np.maximum(denom, 1e-9), 0.0)
            dX = np.zeros_like(X)
            cnt = np.zeros(X.shape[0])
            np.add.at(dX, self.hi, -(lam * w1)[:, None] * g1)
            np.add.at(dX, self.hj, -(lam * w2)[:, None] * g2)
            np.add.at(dX, self.hk, -(lam * w3)[:, None] * g3)
            np.add.at(dX, self.hl, -(lam * w4)[:, None] * g4)
            np.add.at(cnt, self.hi, 1.0)
            np.add.at(cnt, self.hj, 1.0)
            np.add.at(cnt, self.hk, 1.0)
            np.add.at(cnt, self.hl, 1.0)
            # multiple hinges can share a vertex; average their (Jacobi-
            # batched, since numpy can't do true sequential Gauss-Seidel
            # here) corrections rather than summing them unchecked, which
            # keeps the update stable at high-valence vertices near the hub
            dX /= np.maximum(cnt, 1.0)[:, None]
            dX[self.pinned] = 0.0
            X += dX

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
        """PURE RIGID fold — the paper bends ONLY where the crease pattern has
        a declared mountain/valley/diagonal line, and nowhere else. Every
        frame is a rigid composition of the crease pattern folded to a partial
        angle (`_rigid_positions`): each real crease opens to its scheduled
        mountain/valley angle and every facet stays exactly flat (both
        triangles of a cell share the same rigid transform). Nothing else
        touches the geometry — NO relaxation, NO compaction driver, NO facet
        flex. On the seam-split mesh this rigid fold is seam-consistent at
        every fraction (measured 0% vertex disagreement), so no reconciliation
        is needed. This is a hard project invariant: the fold must occur only
        on the crease pattern (see CLAUDE.md) — do not add any pass here that
        moves geometry off the creases.

        The UI's foldness (0-100%, `s` below) is mapped onto
        `[0, self.safe_fold_fraction]`, NOT `[0, 1]` directly: folding this
        pattern's creases all the way to their full declared angles with
        rigid, unflexed facets was measured to self-intersect (real
        triangle-triangle crossings, not just close proximity), and with no
        facet allowed to flex, the fold amount is the only remaining lever
        to prevent that — see `_compute_safe_fold_fraction`. 100% UI foldness
        therefore reaches the deepest fold this exact pattern can rigidly
        reach without any panel passing through another; it does not reach
        the pattern's full nominal closure angle."""
        frames = [np.round(self.flat, 4).reshape(-1).tolist()]
        samples = [0.0]
        for step in range(1, STEPS + 1):
            t = step / STEPS
            s = self._smoothstep(t)
            X = self._rigid_positions(s * self.safe_fold_fraction)
            frames.append(np.round(self._spun_for_display(X, s), 4).reshape(-1).tolist())
            samples.append(t)
        return samples, frames


def solve_sweep(pattern: CreasePattern, params: FlasherParams):
    return FlasherFoldSolver(pattern, params).solve_sweep()
